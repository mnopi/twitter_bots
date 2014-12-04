# -*- coding: utf-8 -*-
import random

from django.db import models
from django.db.models import Count, Q
import simplejson
import tweepy
import time
from project.exceptions import RateLimitedException, AllFollowersExtracted, AllHashtagsExtracted, TweetCreationException
from project.managers import TargetUserManager, TweetManager, ProjectManager, ExtractorManager, ProxiesGroupManager, \
    TwitterUserManager
from scrapper.utils import is_gte_than_days_ago, utc_now, is_lte_than_seconds_ago, naive_to_utc
from twitter_bots import settings


class Project(models.Model):
    name = models.CharField(max_length=100, null=False, blank=True)
    is_running = models.BooleanField(default=True)
    has_tracked_clicks = models.BooleanField(default=False)

    # RELATIONSHIPS
    target_users = models.ManyToManyField('TargetUser', related_name='projects', blank=True)
    hashtags = models.ManyToManyField('Hashtag', related_name='projects', blank=True)

    objects = ProjectManager()

    def __unicode__(self):
        return self.name

    # GETTERS

    def get_twitter_users_unmentioned_by_bot(self, bot, limit=None):
        return TwitterUser.objects.raw("""SELECT
                #count(DISTINCT total_project_users.id) as count
                #DISTINCT(total_project_users.id), total_project_users.created_date
                distinct(total_project_users.id)
            FROM
            (
                (
                    select project_twitteruser.id, project_twitteruser.last_tweet_date from
                    project_twitteruser
                        LEFT OUTER JOIN
                    project_follower ON (project_twitteruser.id = project_follower.twitter_user_id)
                        LEFT OUTER JOIN
                    project_targetuser ON (project_follower.target_user_id = project_targetuser.id)
                        LEFT OUTER JOIN
                    project_project_target_users ON (project_targetuser.id = project_project_target_users.targetuser_id)
                    WHERE project_project_target_users.project_id = %(project_id)d
                )
                union all
                (
                    select project_twitteruser.id, project_twitteruser.last_tweet_date from
                    project_twitteruser
                        LEFT OUTER JOIN
                    project_twitteruserhashashtag ON (project_twitteruser.id = project_twitteruserhashashtag.twitter_user_id)
                        LEFT OUTER JOIN
                    project_hashtag ON (project_twitteruserhashashtag.hashtag_id = project_hashtag.id)
                        LEFT OUTER JOIN
                    project_project_hashtags ON (project_hashtag.id = project_project_hashtags.hashtag_id)
                    WHERE project_project_hashtags.project_id = %(project_id)d
                )
            ) total_project_users

            LEFT OUTER JOIN
                project_tweet_mentioned_users ON (total_project_users.id = project_tweet_mentioned_users.twitteruser_id)
            LEFT OUTER JOIN
                project_tweet ON (project_tweet_mentioned_users.tweet_id = project_tweet.id)
            WHERE
                (
                    (
                        project_tweet_mentioned_users.tweet_id IS NOT NULL
                        AND NOT
                            (
                                total_project_users.id IN
                                    (
                                        SELECT U1.twitteruser_id
                                        FROM project_tweet_mentioned_users U1
                                        INNER JOIN project_tweet U2 ON (U1.tweet_id = U2.id)
                                        WHERE U2.bot_used_id = %(bot_id)d
                                    )
                            )
                    )
                    OR project_tweet_mentioned_users.tweet_id IS NULL
                )

            ORDER BY total_project_users.last_tweet_date DESC

            %(limit)s
            """
            %
            {
                'project_id': self.pk,
                'bot_id': bot.pk,
                'limit': 'limit %d' % limit if limit else '',
            }
        )

    def get_tweets_pending_to_send(self):
        return Tweet.objects.filter(project=self)

    def get_followers(self):
        """Saca los usuarios que son followers a partir de un proyecto"""
        return Follower.objects.filter(target_user__projects=self)

    def get_hashtagers(self):
        """Saca los usuarios que son followers a partir de un proyecto"""
        return TwitterUserHasHashtag.objects.filter(hashtag__projects=self)

    def get_total_users(self):
        return TwitterUser.objects.for_project(self)

    def get_mentioned_users(self):
        return self.get_total_users().filter(mentions__project=self)

    def get_unmentioned_users(self):
        return TwitterUser.objects.unmentioned_on_project(self)

    def get_followers_to_mention(self):
        project_followers = self.get_followers()
        project_followers = project_followers.annotate(mentions_count=Count('twitter_user__mentions'))
        return project_followers.filter(mentions_count=0)

    def has_all_mentioned(self):
        pass
        # return self.filter(target_users__followers)

    def get_platforms(self, only_select=None):
        "saca lista de las plataformas para las que hay enlaces creados en el proyecto"
        platforms = Link.objects.filter(project=self).values('platform').distinct()
        return [pl['platform'] for pl in platforms]

    def get_twitteable_bots(self):
        """Saca, de sus grupos de proxies asignados, aquellos bots que las usen y puedan tuitear"""
        from core.models import TwitterBot
        return TwitterBot.objects.using_in_project(self).twitteable()

    def check_if_has_minimal_content(self):
        """Verifica si el proyecto tiene asignado el contenido suficiente para poderse fabricar tweets para él"""
        if not self.tweet_msgs.exists():
            settings.LOGGER.error('Project "%s" has no tweet_mgs defined' % self.__unicode__())
            raise Exception()

        if not self.links.exists():
            settings.LOGGER.error('Project "%s" has no links defined' % self.__unicode__())
            raise Exception()


class TweetMsg(models.Model):
    text = models.CharField(max_length=101, null=False, blank=False)
    # proyecto nulo es mensaje de un feed por ejemplo
    project = models.ForeignKey(Project, null=True, blank=True, related_name='tweet_msgs')
    language = models.CharField(max_length=2, null=True, blank=True)

    def __unicode__(self):
        return '%s @ %s' % (self.text, self.project.name) if self.project else self.text


class TargetUser(models.Model):
    username = models.CharField(max_length=80, null=False, blank=True)
    # cuando el cursor sea null es que se han extraido todos sus followers
    next_cursor = models.BigIntegerField(null=True, default=0)
    followers_count = models.PositiveIntegerField(null=True, default=0)

    # fecha en la que se dieron los últimos pagebreaks
    last_pagebreaks_date = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    # REL
    twitter_users = models.ManyToManyField('TwitterUser', through='Follower',
                                           related_name='target_users', blank=True)

    objects = TargetUserManager()

    def __unicode__(self):
        return self.username

    def followers_saved(self):
        return Follower.objects.filter(target_user=self).count()

    def followers_android(self):
        return Follower.objects.filter(target_user=self, twitter_user__source=TwitterUser.ANDROID).count()


class Follower(models.Model):
    target_user = models.ForeignKey(TargetUser, related_name='followers', null=False)
    twitter_user = models.ForeignKey('TwitterUser', related_name='follower', null=False)
    date_saved = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s -> %s' % (self.twitter_user, self.target_user)

    def was_mentioned(self, project=None):
        """Mira si el follower aparece mencionado para todos los proyectos o el dado por parametro"""
        tweets = Tweet.objects.filter(mentioned_users__follower=self)
        if project:
            tweets = tweets.filter(project=project)
        if tweets:
            return True
        else:
            return False


class TwitterUser(models.Model):
    DEFAULT_LANG = 'en'
    OTHERS = 0
    IOS = 1
    IPAD = 2
    IPHONE = 3
    ANDROID = 4
    SOURCES = (
        (OTHERS, 'others'),
        (IOS, 'ios'),
        (IPAD, 'ipad'),
        (IPHONE, 'iphone'),
        (ANDROID, 'android'),
    )
    source = models.PositiveIntegerField(null=False, choices=SOURCES, default=0)
    username = models.CharField(max_length=160, null=False)
    full_name = models.CharField(max_length=160, null=True)
    twitter_id = models.BigIntegerField(null=False)

    # GEO
    geo_enabled = models.BooleanField(default=False)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    city = models.CharField(max_length=80, null=True)
    country = models.CharField(max_length=2, null=True)

    # TIME
    created_date = models.DateTimeField(null=False)
    time_zone = models.CharField(max_length=50, null=True)  # te da la zona horaria por la ciudad, x. ej 'Madrid'
    last_tweet_date = models.DateTimeField(db_index=True, null=True)

    language = models.CharField(max_length=2, null=False, default=DEFAULT_LANG)
    followers_count = models.PositiveIntegerField(null=True)
    tweets_count = models.PositiveIntegerField(null=True)
    verified = models.BooleanField(default=False)
    date_saved = models.DateTimeField(auto_now_add=True)

    objects = TwitterUserManager()

    def __unicode__(self):
        return self.username

    def is_active(self):
        try:
            if self.last_tweet_date:
                # si ha tuiteado vemos lo viejo que es el último tweet
                return is_gte_than_days_ago(self.last_tweet_date, settings.MAX_DAYS_SINCE_LAST_TWEET)
            else:
                # si no ha tuiteado nunca, entonces vemos lo nuevo que es
                return is_gte_than_days_ago(self.created_date, settings.MAX_DAYS_SINCE_REGISTERED_ON_TWITTER_WITHOUT_TWEETS)
        except Exception as e:
            raise e


class Tweet(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)  # la fecha en la que se crea y se mete en la cola
    date_sent = models.DateTimeField(null=True, blank=True)
    sending = models.BooleanField(default=False)
    sent_ok = models.BooleanField(default=False)

    # RELATIONSHIPS
    tweet_msg = models.ForeignKey(TweetMsg, null=True)
    link = models.ForeignKey('Link', null=True, blank=True, related_name='tweets')
    page_announced = models.ForeignKey('PageLink', null=True, blank=True, related_name='tweets')
    bot_used = models.ForeignKey('core.TwitterBot', related_name='tweets', null=True)
    mentioned_users = models.ManyToManyField(TwitterUser, related_name='mentions', null=True, blank=True)
    project = models.ForeignKey(Project, null=True, blank=True, related_name="tweets")
    tweet_img = models.ForeignKey('TweetImg', null=True, blank=True)

    objects = TweetManager()

    def __unicode__(self):
        return self.compose()

    def compose(self):
        compose_txt = ''
        if self.mentioned_users:
            mu_txt = ''
        # solo se podrá consultar los usuarios mencionados si antes se guardó la instancia del tweet en BD
            for mu in self.mentioned_users.all():
                mu_txt += '@%s ' % mu.username
            compose_txt += mu_txt
        if self.tweet_msg:
            compose_txt += self.tweet_msg.text
        if self.link:
            compose_txt += ' ' + self.link.url if self.link else ''
        if self.page_announced:
            pa = self.page_announced
            if self.tweet_msg or self.link:
                compose_txt += ' '
            if pa.page_title and pa.hashtag:
                compose_txt += pa.page_title + ' ' + pa.page_link + ' ' + pa.hashtag.name
            elif pa.page_title:
                compose_txt += pa.page_title + ' ' + pa.page_link
            elif pa.hashtag:
                compose_txt += pa.page_link + ' ' + pa.hashtag.name
            else:
                compose_txt += pa.page_link

        return compose_txt

    def length(self):
        def mentioned_users_space():
            length = 0
            for mu in self.mentioned_users.all():
                length += len(mu.username) + 2
            return length

        total_length = 0
        if self.mentioned_users:
            total_length += mentioned_users_space()
        if self.tweet_msg:
            total_length += len(self.tweet_msg.text)
        if self.link:
            total_length += 1 + 22
        if self.tweet_img:
            total_length += 23
        if self.page_announced:
            if self.tweet_msg or self.link:
                total_length += 1
            total_length += self.page_announced.page_link_length()

        return total_length

    def has_space(self):
        """Devuelve si el tweet no supera los 140 caracteres"""
        return self.length() < 140

    def exceeded_tweet_limit(self):
        return self.length() > 140

    def has_image(self):
        return self.tweet_img != None

    def is_available(self):
        return not self.sending and not self.sent_ok

    def add_mentions(self, bot_used, project):
        if self.tweet_msg:
            language = self.tweet_msg.language
        else:
            language = None

        unmentioned_for_tweet_to_send = TwitterUser.objects.get_unmentioned_on_project(
                    project,
                    limit=bot_used.get_group().max_num_mentions_per_tweet,
                    language=language
                )

        if unmentioned_for_tweet_to_send:
            for unmentioned in unmentioned_for_tweet_to_send:
                if self.length() + len(unmentioned.username) + 2 <= 140:
                    self.mentioned_users.add(unmentioned)
                else:
                    break

            settings.LOGGER.info('Queued [proj: %s | bot: %s] >> %s' %
                                 (project.__unicode__(), bot_used.__unicode__(), self.compose()))
            # break
        else:
            settings.LOGGER.warning('Bot %s has not more users to mention for project %s' %
                                    (bot_used.username, project.name))
            raise TweetCreationException(self)

    def add_tweet_msg(self, project):
        tweet_message = project.tweet_msgs.order_by('?')[0]
        if self.length() + len(tweet_message.text) <= 140:
            self.tweet_msg = tweet_message
        else:
            settings.LOGGER.warning('Tweet %s is too long to add custom message %s' %
                                    (self, tweet_message))

    def add_page_announced(self, project):
        page_announced = project.pagelink_set.order_by('?')[0]
        if self.length() + page_announced.page_link_length() <= 140:
            self.page_announced = page_announced
        else:
            settings.LOGGER.warning('Tweet %s is too long to add page link %s' %
                                    (self, page_announced))

    def add_image(self, project):
        if self.length() + 23 <= 140:
            self.tweet_img = project.tweet_imgs.order_by('?')[0]
        else:
            settings.LOGGER.warning('Tweet %s is too long to add image' %
                                    (self))

    def add_link(self, project):
        link = project.links.get(is_active=True)
        if self.length() + len(link.url) + 1 <= 140:
            self.link = link
        else:
            settings.LOGGER.warning('Tweet %s is too long to add link %s' %
                                    (self, link))

    def send(self):
        try:
            settings.LOGGER.info('Bot %s sending tweet %i: >> %s' %
                                 (self.bot_used.__unicode__(), self.pk, self.compose()))
            self.bot_used.scrapper.set_screenshots_dir(str(self.pk))
            self.bot_used.scrapper.open_browser()
            self.bot_used.scrapper.login()
            self.bot_used.scrapper.send_tweet(self)
            self.sent_ok = True
            self.date_sent = utc_now()
            self.save()
        except Exception as e:
            settings.LOGGER.exception('Error sending tweet (id: %i, bot: %s - %s)' %
                                      (self.pk, self.bot_used.username, self.bot_used.real_name))
            raise e
        finally:
            # si el tweet sigue en BD se desmarca como enviando
            if Tweet.objects.filter(pk=self.pk).exists():
                self.sending = False
                self.save()
            self.bot_used.scrapper.close_browser()

    def has_bot_sending_another(self):
        """Comprueba si el bot asignado para el tweet ya está enviando otro"""
        return Tweet.objects.filter(sending=True, bot_used=self.bot_used).exists()

    def has_enough_time_spend_before_sending(self):
        """
            Indica si ha pasado el suficientemente tiempo para poder lanzarse este tweet tras el último
            que lanzó su robot. Por ejemplo, si su robot pertenece a un grupo de intervalo '2-7' minutos,
            entonces indicará si pasó ese tiempo en caso de haber lanzado algún tweet antes
        """
        last_tweet_sent = self.bot_used.get_last_tweet_sent()
        if not last_tweet_sent or not last_tweet_sent.date_sent:
            return True
        else:
            # si el bot ya envió algún tweet se comprueba que el último se haya enviado
            # antes o igual a la fecha de ahora menos el tiempo aleatorio entre tweets por bot
            time_between_tweets = self.bot_used.get_group().time_between_tweets.split('-')
            random_seconds_ago = random.randint(60*int(time_between_tweets[0]), 60*int(time_between_tweets[1]))
            if is_lte_than_seconds_ago(last_tweet_sent.date_sent, random_seconds_ago):
                return True
            else:
                return False

    def can_be_sent(self):
        return not self.has_bot_sending_another() and self.has_enough_time_spend_before_sending()


class Link(models.Model):
    url = models.URLField(null=False)
    # si project es null es que es un link de algún feed
    project = models.ForeignKey(Project, null=True, blank=True, related_name='links')
    is_active = models.BooleanField(default=True)

    def __unicode__(self):
        return '%s @ %s' % (self.project.name, self.url) if self.project else self.url


class Sublink(models.Model):
    IOS = 0
    ANDROID = 1
    DESKTOP = 2
    PLATFORMS = (
        (IOS, 'Ios'),
        (ANDROID, 'Android'),
        (DESKTOP, 'Escritorio')
    )
    url = models.URLField(null=False)
    parent_link = models.ForeignKey(Link, related_name='sublinks')
    platform = models.IntegerField(null=True, blank=True, choices=PLATFORMS, default=0)
    language = models.CharField(max_length=2,
                                choices=settings.LANGUAGES,
                                default=settings.ENGLISH)


class Extractor(models.Model):
    # consumer_key = "ESjshGwY13JIl3SLF4dLiQVDB"
    # consumer_secret = "QFD2w79cXOXoGOf1TDbcSxPEhVJWtjGhMHrFTkTiouwreg9nJ3"
    # access_token = "2532144721-eto2YywaV7KF0gmrHLhYSWiZ8X22xt8KuTItV83"
    # access_token_secret = "R6zdO3qVsLP0RuyTN25nCqfxvtCyUydOVzFn8NCzJezuG"
    BASE_URL = 'https://api.twitter.com/1.1/'

    consumer_key = models.CharField(null=False, max_length=200)
    consumer_secret = models.CharField(null=False, max_length=200)
    access_token = models.CharField(null=False, max_length=200)
    access_token_secret = models.CharField(null=False, max_length=200)
    twitter_bot = models.OneToOneField('core.TwitterBot', null=False, related_name='extractor')
    date_created = models.DateTimeField(auto_now_add=True)
    last_request_date = models.DateTimeField(null=True, blank=True)
    is_rate_limited = models.BooleanField(default=False)
    minutes_window = models.PositiveIntegerField(null=True)

    FOLLOWER_MODE = 1
    HASHTAG_MODE = 2
    MODES = (
        (FOLLOWER_MODE, 'follower mode'),
        (HASHTAG_MODE, 'hashtag mode'),
    )
    mode = models.PositiveIntegerField(null=False, choices=MODES)

    objects = ExtractorManager()

    def __unicode__(self):
        return self.twitter_bot.username

    def connect_twitter_api(self):
        """
            Antes de conectar comprobamos que el proxy no esté anticuado
        """
        if not self.twitter_bot.proxy_for_usage.is_in_proxies_txts:
            self.twitter_bot.assign_proxy()

        auth = tweepy.OAuthHandler(self.consumer_key, self.consumer_secret)
        auth.set_access_token(self.access_token, self.access_token_secret)
        self.api = tweepy.API(auth, proxy=self.twitter_bot.proxy_for_usage.proxy)

    def get(self, uri):
        # url = 'https://api.twitter.com/1.1/followers/list.json?cursor=2&screen_name=candycrush&count=5000'
        resp = self.api.get(self.BASE_URL + uri)
        return simplejson.loads(resp.content)

    def get_user_info(self, username):
        return self.get('users/show.json?screen_name=%s' % username)

    # def format_datetime(self, twitter_datetime_str):
    #     if not twitter_datetime_str:
    #         return None
    #     else:
    #         return datetime.datetime.strptime(twitter_datetime_str, '%a %b %d %H:%M:%S +0000 %Y')

    def format_source(self, user_source_str):
        low = user_source_str.lower()
        if 'iphone' in low:
            return TwitterUser.IPHONE
        elif 'ipad' in low:
            return TwitterUser.IPAD
        elif 'ios' in low:
            return TwitterUser.IOS
        elif 'android' in low:
            return TwitterUser.ANDROID
        else:
            return TwitterUser.OTHERS

    def update_target_user_data(self, target_user):
        tw_user = self.api.get_user(screen_name=target_user.username)
        target_user.followers_count = tw_user.followers_count
        target_user.save()

    def create_twitter_user_obj(self, tw_user_from_api):
        "tw_follower es el objeto devuelto por tweepy tras consultar la API"
        twitter_user = TwitterUser.objects.filter(twitter_id=tw_user_from_api.id)
        if twitter_user.exists():
            if twitter_user.count() > 1:
                raise Exception('Duplicated twitter user with id %i' % twitter_user[0].twitter_id)
            else:
                settings.LOGGER.info('Twitter user %s already exists' % twitter_user[0].username)
                return twitter_user[0], False
        else:
            twitter_user = TwitterUser()
            twitter_user.twitter_id = tw_user_from_api.id
            twitter_user.created_date = naive_to_utc(tw_user_from_api.created_at)
            twitter_user.followers_count = tw_user_from_api.followers_count
            twitter_user.geo_enabled = tw_user_from_api.geo_enabled
            twitter_user.language = tw_user_from_api.lang[:2] if tw_user_from_api.lang else TwitterUser.DEFAULT_LANG
            twitter_user.full_name = tw_user_from_api.name
            twitter_user.username = tw_user_from_api.screen_name
            twitter_user.tweets_count = tw_user_from_api.statuses_count
            twitter_user.time_zone = tw_user_from_api.time_zone
            twitter_user.verified = tw_user_from_api.verified

            if hasattr(tw_user_from_api, 'status'):
                if hasattr(tw_user_from_api.status, 'created_at'):
                    twitter_user.last_tweet_date = naive_to_utc(tw_user_from_api.status.created_at)
                if hasattr(tw_user_from_api.status, 'source'):
                    twitter_user.source = self.format_source(tw_user_from_api.status.source)
                else:
                    twitter_user.source = TwitterUser.OTHERS
            else:
                twitter_user.source = TwitterUser.OTHERS

            return twitter_user, True

    def extract_followers(self, target_user, skip_page_on_existing=False):
        from project.management.commands.run_extractors import mutex

        self.update_target_user_data(target_user)

        params = {
            'screen_name': target_user.username,
            'count': 200,
        }
        if target_user.next_cursor:
            params.update({'cursor': target_user.next_cursor})

        cursor = tweepy.Cursor(self.api.followers, **params)

        try:
            num_page_breaks = 0  # cuenta el número de veces que se encontró página con followers ya existentes
            num_pages_retrieved = 0

            for page in cursor.pages():
                if num_pages_retrieved == settings.MAX_PAGES_RETRIEVED_PER_TARGET_USER:
                    break
                else:
                    mutex.acquire()

                    self.last_request_date = utc_now()
                    self.save()
                    settings.LOGGER.info("""Retrieved @%s\'s follower page with cursor %i
                        \n\tNext cursor: %i
                        \n\tPrevious cursor: %i
                    """ % (target_user.username, target_user.next_cursor, cursor.iterator.next_cursor,
                           cursor.iterator.prev_cursor))

                    new_twitter_users = []
                    new_followers = []
                    # guardamos cada follower recibido, sin duplicar en BD
                    for tw_follower in page:
                        # creamos twitter_user a partir del follower si ya no existe en BD
                        twitter_user, is_new = self.create_twitter_user_obj(tw_follower)
                        if is_new:
                            if twitter_user.is_active():
                                new_twitter_users.append(twitter_user)
                                settings.LOGGER.info('New twitter user %s added to list' % twitter_user.__unicode__())
                            else:
                                settings.LOGGER.info('Twitter user %s inactive. LTD: %s, CD: %s' %
                                                     (twitter_user.__unicode__(), twitter_user.last_tweet_date, twitter_user.created_date))
                        else:
                            follower = Follower(twitter_user=twitter_user, target_user=target_user)
                            follower_already_exists = Follower.objects.select_related('twitter_user', 'target_user').filter(
                                twitter_user=twitter_user, target_user=target_user).exists()
                            if follower_already_exists:
                                if skip_page_on_existing:
                                    settings.LOGGER.info('Follower %s already exists, skipping page..' % follower.__unicode__())
                                    num_page_breaks += 1
                                    break
                                else:
                                    settings.LOGGER.info('Follower %s already exists' % follower.__unicode__())
                            elif follower.twitter_user.is_active():
                                new_followers.append(follower)
                                settings.LOGGER.info('New follower %s added to list' % follower.__unicode__())

                    before_saving = utc_now()
                    time.sleep(2)  # para que se note la diferencia por si guarda muy rapido los twitterusers
                    TwitterUser.objects.bulk_create(new_twitter_users)
                    # pillamos todos los ids de los nuevos twitter_user creados
                    new_twitter_users_ids = TwitterUser.objects\
                        .filter(date_saved__gt=before_saving)\
                        .values_list('id', flat=True)

                    mutex.release()

                    for twitter_user in new_twitter_users_ids:
                        new_followers.append(
                            Follower(twitter_user_id=twitter_user, target_user=target_user))

                    Follower.objects.bulk_create(new_followers)

                    if num_page_breaks > settings.MAX_PAGE_BREAKS_EXTRACTING_FOLLOWERS:
                        # dejamos de extraer ese target user
                        target_user.next_cursor = None
                        target_user.last_pagebreaks_date = utc_now()
                        target_user.save()
                        settings.LOGGER.info('Exceeded %i page breaks limit extracting followers from %s' %
                                             (settings.MAX_PAGE_BREAKS_EXTRACTING_FOLLOWERS, target_user.username))
                        break
                    elif target_user.next_cursor is None:
                        # si el cursor actual es None y no se superó el num de page breaks es que todos los followers
                        # se extrayeron ok
                        settings.LOGGER.info('All followers from %s retrieved ok' % target_user.username)
                    else:
                        # en cualquier otro caso actualizamos el next_cursor para el target user
                        target_user.next_cursor = cursor.iterator.next_cursor
                        target_user.save()

                    num_pages_retrieved += 1

        except tweepy.error.TweepError as ex:
            if hasattr(ex.response, 'status_code') and ex.response.status_code == 429:
                raise RateLimitedException(self)
            else:
                settings.LOGGER.exception('')
                time.sleep(7)
                raise ex

    def extract_hashtag_users(self, hashtag):
        from project.management.commands.run_extractors import mutex

        self.connect_twitter_api()

        while True:
            results = self.api.search(
                q=hashtag.q,
                geocode=hashtag.geocode,
                lang=hashtag.lang,
                result_type=hashtag.result_type,
                max_id=hashtag.max_id,
                count=100,
            )

            mutex.acquire()

            self.last_request_date = utc_now()
            self.save()
            settings.LOGGER.info('Retrieved 100 tweets for hashtag "%s" (max_id=%s)' %
                                 (hashtag.q, str(hashtag.max_id)))

            new_twitter_users = []
            new_hashtag_users = []

            for result in results:

                # vemos si ya estaba en los pendientes de grabar en BD
                is_repeated = False
                for new_tw_user in new_twitter_users:
                    if result.user.id == new_tw_user.twitter_id:
                        is_repeated = True
                        break

                if not is_repeated:
                    twitter_user, is_new = self.create_twitter_user_obj(result.user)
                    if is_new:
                        new_twitter_users.append(twitter_user)
                        settings.LOGGER.info('New twitter user %s added to list' % twitter_user.__unicode__())
                    else:
                        if hashtag.twitter_users.filter(pk=twitter_user.pk).exists():
                            settings.LOGGER.info('Twitter user %s already exists for hashtag %s' %
                                                 (twitter_user.__unicode__(), hashtag.__unicode__()))
                        else:
                            new_hashtag_users.append(
                                TwitterUserHasHashtag(twitter_user_id=twitter_user.pk, hashtag=hashtag)
                            )
                            settings.LOGGER.info('New twitter user %s added for hashtag %s' %
                                                 (twitter_user.__unicode__(), hashtag.__unicode__()))

            before_saving = utc_now()
            time.sleep(2)  # para que se note la diferencia por si guarda muy rapido los twitterusers
            TwitterUser.objects.bulk_create(new_twitter_users)
            # pillamos todos los ids de los nuevos twitter_user creados
            new_twitter_users_ids = TwitterUser.objects\
                .filter(date_saved__gt=before_saving)\
                .values_list('id', flat=True)

            mutex.release()

            for twitter_user_id in new_twitter_users_ids:
                new_hashtag_users.append(
                    TwitterUserHasHashtag(twitter_user_id=twitter_user_id, hashtag=hashtag)
                )

            TwitterUserHasHashtag.objects.bulk_create(new_hashtag_users)

            # actualizamos el max_id para siguiente petición
            last_tweet = results[-1]
            hashtag.max_id = last_tweet.id

            # comprobamos si supera el límite de antiguedad
            if hashtag.older_limit_for_tweets and last_tweet.created_at < hashtag.older_limit_for_tweets:
                settings.LOGGER.info('Older date limit reached for tweets by hashtag "%s"' % hashtag.__unicode__())
                hashtag.is_extracted = True
                break
            # si supera el límite de usuarios
            elif hashtag.max_user_count and hashtag.twitter_users.count() > hashtag.max_user_count:
                settings.LOGGER.info('User count limit reached for tweets by hashtag "%s"' % hashtag.__unicode__())
                hashtag.is_extracted = True
                break

            hashtag.save()

    def extract_followers_from_all_target_users(self):
        self.connect_twitter_api()

        while True:
            target_users_to_extract = TargetUser.objects.available_to_extract()
            if target_users_to_extract.exists():
                for target_user in target_users_to_extract:
                    self.extract_followers(target_user, skip_page_on_existing=True)
            else:
                raise AllFollowersExtracted()

    def extract_twitter_users_from_all_hashtags(self):
        hashtags_to_extract = Hashtag.objects.filter(projects__is_running=True, is_extracted=False)
        if hashtags_to_extract.exists():
            hashtag = hashtags_to_extract.first()
            self.extract_hashtag_users(hashtag)
        else:
            raise AllHashtagsExtracted()

    def is_available(self):
        """Si fue marcadado como rate limited se mira si pasaron más de 15 minutos.
        En ese caso se desmarca y se devielve True"""
        if self.is_rate_limited:
            seconds_lapsed = (utc_now() - self.last_request_date).seconds
            if seconds_lapsed > self.minutes_window * 60:
                self.is_rate_limited = False
                self.save()
                return True
            else:
                return False
        else:
            return True


class Hashtag(models.Model):
    q = models.CharField(max_length=140, null=False)
    geocode = models.CharField(max_length=50, null=True, blank=True)
    lang = models.CharField(max_length=2, null=True, blank=True)
    MIXED = 1
    RECENT = 2
    POPULAR = 3
    RESULT_TYPES = (
        (MIXED, 'mixed'),
        (RECENT, 'recent'),
        (POPULAR, 'popular'),
    )
    result_type = models.PositiveIntegerField(null=False, choices=RESULT_TYPES, default=2)
    max_id = models.BigIntegerField(null=True, blank=True)
    older_limit_for_tweets = models.DateTimeField(null=True, blank=True)
    max_user_count = models.IntegerField(null=True, blank=True)
    is_extracted = models.BooleanField(default=False)

    twitter_users = models.ManyToManyField('TwitterUser', through='TwitterUserHasHashtag',
                                           related_name='hashtags', blank=True)

    def __unicode__(self):
        return self.q


class TwitterUserHasHashtag(models.Model):
    hashtag = models.ForeignKey(Hashtag, related_name='hashtag_users', null=False)
    twitter_user = models.ForeignKey(TwitterUser, related_name='hashtag_users', null=False)
    date_saved = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s %s' % (self.twitter_user.username, self.hashtag.q)


class TweetImg(models.Model):
    # def get_img_path(self, filename):
    #     if self.pk:
    #         path = '%s/photos/cat_%s/photo_%s.jpg' % \
    #         fileName, fileExtension = os.path.splitext(filename)
    #         (self.country.upper(), self.category.id, self.id)
    #     return prepend_env_folder(path)

    img = models.ImageField(upload_to='tweet_images', blank=True, null=True)
    is_using = models.BooleanField(default=True)
    project = models.ForeignKey(Project, null=False, related_name='tweet_imgs')

    def __unicode__(self):
        return '%s @ %s' % (self.img.path, self.project.name)


class PageLinkHashtag(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False)

    def __unicode__(self):
        return self.name


class PageLink(models.Model):
    page_title = models.CharField(max_length=150, null=True, blank=True)
    page_link = models.URLField(null=False, blank=False)
    project = models.ForeignKey(Project, null=False, blank=False)
    is_active = models.BooleanField(default=True)
    hashtag = models.ForeignKey(PageLinkHashtag, null=True, blank=True, related_name="page_links")

    def __unicode__(self):
        return self.page_title

    def page_link_length(self):
        page_link_length = 22
        if self.page_title:
            page_link_length += 1 + len(self.page_title)
        if self.hashtag:
            page_link_length += 1 + len(self.hashtag.name)
        return page_link_length


class ProxiesGroup(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False)

    # bot registration
    is_bot_creation_enabled = models.BooleanField(default=False)
    max_tw_bots_per_proxy_for_registration = models.PositiveIntegerField(null=False, blank=False, default=6)
    min_days_between_registrations_per_proxy = models.PositiveIntegerField(null=False, blank=False, default=5)

    # indica si vamos a reutilizar proxies con bots chungos (por ejemplo para grupos de prueba etc)
    reuse_proxies_with_suspended_bots = models.BooleanField(default=False)

    # bot usage
    is_bot_usage_enabled = models.BooleanField(default=False)
    max_tw_bots_per_proxy_for_usage = models.PositiveIntegerField(null=False, blank=False, default=12)
    time_between_tweets = models.CharField(max_length=10, null=False, blank=False, default='2-5')  # '2-5' -> entre 2 y 5 minutos
    max_num_mentions_per_tweet = models.PositiveIntegerField(null=False, blank=False, default=1)

    has_tweet_msg = models.BooleanField(default=False)
    has_link = models.BooleanField(default=False)
    has_tweet_img = models.BooleanField(default=False)
    has_page_announced = models.BooleanField(default=False)
    has_mentions = models.BooleanField(default=False)

    # webdriver
    FIREFOX = 'FI'
    CHROME = 'CH'
    PHANTOMJS = 'PH'
    WEBDRIVERS = (
        ('FI', 'Firefox'),
        ('CH', 'Chrome'),
        ('PH', 'PhantomJS'),
    )
    webdriver = models.CharField(max_length=2, choices=WEBDRIVERS, default='PH')

    # RELATIONSHIPS
    projects = models.ManyToManyField(Project, related_name='proxies_groups', null=True, blank=True)

    objects = ProxiesGroupManager()

    def __unicode__(self):
        return self.name
