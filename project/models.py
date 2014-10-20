# -*- coding: utf-8 -*-


import datetime
from django.db import models
from django.db.models import Count, Q
import pytz
import simplejson
import tweepy
import time
from core.models import TwitterBot
from project.exceptions import RateLimitedException
from project.managers import TargetUserManager, TweetManager, ProjectManager, ExtractorManager
from twitter_bots import settings


class Project(models.Model):
    name = models.CharField(max_length=100, null=False, blank=True)
    hashtags = models.ManyToManyField('Hashtag', related_name='projects', blank=True)
    is_running = models.BooleanField(default=True)
    has_tracked_clicks = models.BooleanField(default=False)

    # RELATIONSHIPS
    target_users = models.ManyToManyField('TargetUser', related_name='projects', blank=True)

    objects = ProjectManager()

    def __unicode__(self):
        return self.name

    # GETTERS

    def get_tweets_pending_to_send(self):
        return Tweet.objects.filter(project=self, sent_ok=False, sending=False)

    def get_followers(self, platform=None):
        """Saca los usuarios que son followers a partir de un proyecto"""
        total_followers = Follower.objects.filter(target_user__projects=self)
        if platform:
            return total_followers.filter(twitter_user__source=platform)
        else:
            return total_followers

    def get_hashtagers(self, platform=None):
        """Saca los usuarios que son followers a partir de un proyecto"""
        total_hashtagers = TwitterUserHasHashtag.objects.filter(hashtag__projects=self)
        if platform:
            return total_hashtagers.filter(twitter_user__source=platform)
        else:
            return total_hashtagers

    def get_total_users(self, platform=None):
        # total_followers = self.get_followers()
        # total_hashtagers = self.get_hashtagers()
        # return total_followers + total_hashtagers
        total_users = TwitterUser.objects.filter(
            Q(target_users__projects=self) |
            Q(hashtags__projects=self)
        )
        if platform:
            return total_users.filter(source=platform)
        else:
            return total_users

    def get_mentioned_users(self, platform=None):
        return self.get_total_users(platform=platform).exclude(mentions=None).filter(mentions__project=self)

    def get_unmentioned_users(self, platform=None):
        mentioned_pks = self.get_mentioned_users(platform=platform).values_list('id', flat=True)
        return self.get_total_users(platform=platform).exclude(pk__in=mentioned_pks)

    def display_sent_tweets_android(self):
        """ Saca [usuarios_mencionados] / [usuarios_totales]"""
        return '%i / %i' % (
            self.get_mentioned_users(platform=TwitterUser.ANDROID).count(),
            self.get_total_users(platform=TwitterUser.ANDROID).count()
        )

    def get_followers_to_mention(self, platform=None):
        project_followers = self.get_followers(platform=platform)
        project_followers = project_followers.annotate(mentions_count=Count('twitter_user__mentions'))
        return project_followers.filter(mentions_count=0)

    def has_all_mentioned(self):
        pass
        # return self.filter(target_users__followers)

    def get_platforms(self, only_select=None):
        "Only select indicara las plataformas que queremos obtener entre las disponibles para el proyecto"
        platforms = Link.objects.filter(project=self).values('platform').distinct()
        return [pl['platform'] for pl in platforms]


class TweetMsg(models.Model):
    text = models.CharField(max_length=101, null=False, blank=False)
    project = models.ForeignKey(Project, related_name='tweet_msgs')

    def __unicode__(self):
        return '%s @ %s' % (self.text, self.project.name)


class TargetUser(models.Model):
    username = models.CharField(max_length=80, null=False, blank=True)
    # cuando el cursor sea null es que se han extraido todos sus followers
    next_cursor = models.BigIntegerField(null=True, default=0)
    followers_count = models.PositiveIntegerField(null=True, default=0)

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
    last_tweet_date = models.DateTimeField(null=True)

    language = models.CharField(max_length=2, null=False, default=DEFAULT_LANG)
    followers_count = models.PositiveIntegerField(null=True)
    tweets_count = models.PositiveIntegerField(null=True)
    verified = models.BooleanField(default=False)
    date_saved = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.username


class Tweet(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    date_sent = models.DateTimeField(null=True, blank=True)
    sending = models.BooleanField(default=False)
    sent_ok = models.BooleanField(default=False)

    # RELATIONSHIPS
    tweet_msg = models.ForeignKey(TweetMsg, null=False)
    link = models.ForeignKey('Link', null=True, blank=True, related_name='tweet')
    bot_used = models.ForeignKey(TwitterBot, related_name='tweets', null=True)
    mentioned_users = models.ManyToManyField(TwitterUser, related_name='mentions', null=True, blank=True)
    project = models.ForeignKey(Project, related_name="tweets")

    objects = TweetManager()

    def __unicode__(self):
        return self.compose()

    def compose(self):
        mu_txt = ''
        # solo se podrá consultar los usuarios mencionados si antes se guardó la instancia del tweet en BD
        for mu in self.mentioned_users.all():
            mu_txt += '@%s ' % mu.username

        link_txt = ' ' + self.link.url if self.link else ''

        return mu_txt + self.tweet_msg.text + link_txt

    def length(self):
        def mentioned_users_space():
            length = 0
            for mu in self.mentioned_users.all():
                length += len(mu.username) + 2
            return length

        total_lenght = 0
        total_lenght += mentioned_users_space()
        total_lenght += len(self.tweet_msg.text)
        if self.link:
            total_lenght += 1 + len(self.link.url)
        return total_lenght

    def has_space(self):
        """Devuelve si el tweet no supera los 140 caracteres"""
        return self.length() < 140

    def exceeded_tweet_limit(self):
        return self.length() > 140

    def is_available(self):
        return not self.sending and not self.sent_ok


class Link(models.Model):
    url = models.URLField(null=False)
    project = models.ForeignKey(Project, null=False, related_name='links')
    platform = models.IntegerField(null=True, blank=True, choices=TwitterUser.SOURCES, default=0)
    is_active = models.BooleanField(default=True)

    def __unicode__(self):
        return '%s @ %s' % (self.project.name, self.get_platform_display())


class Extractor(models.Model):
    #     consumer_key = "ESjshGwY13JIl3SLF4dLiQVDB"
    #     consumer_secret = "QFD2w79cXOXoGOf1TDbcSxPEhVJWtjGhMHrFTkTiouwreg9nJ3"
    #     access_token = "2532144721-eto2YywaV7KF0gmrHLhYSWiZ8X22xt8KuTItV83"
    #     access_token_secret = "R6zdO3qVsLP0RuyTN25nCqfxvtCyUydOVzFn8NCzJezuG"
    BASE_URL = 'https://api.twitter.com/1.1/'

    consumer_key = models.CharField(null=False, max_length=200)
    consumer_secret = models.CharField(null=False, max_length=200)
    access_token = models.CharField(null=False, max_length=200)
    access_token_secret = models.CharField(null=False, max_length=200)
    twitter_bot = models.OneToOneField(TwitterBot, null=False, related_name='extractor')
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
        # self.api = req.OAuth1Session(self.consumer_key,
        #                              client_secret=self.consumer_secret,
        #                              resource_owner_key=self.access_token,
        #                              resource_owner_secret=self.access_token_secret,
        #                              proxies={'https': self.twitter_bot.proxy})
        auth = tweepy.OAuthHandler(self.consumer_key, self.consumer_secret)
        auth.set_access_token(self.access_token, self.access_token_secret)
        self.api = tweepy.API(auth, proxy=self.twitter_bot.proxy.proxy)

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
            twitter_user.created_date = tw_user_from_api.created_at
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
                    twitter_user.last_tweet_date = tw_user_from_api.status.created_at
                if hasattr(tw_user_from_api.status, 'source'):
                    twitter_user.source = self.format_source(tw_user_from_api.status.source)
                else:
                    twitter_user.source = TwitterUser.OTHERS
            else:
                twitter_user.source = TwitterUser.OTHERS

            return twitter_user, True

    def extract_followers(self, target_user, skip_page_on_existing=False):
        self.connect_twitter_api()

        self.update_target_user_data(target_user)

        params = {
            'screen_name': target_user.username,
            'count': 200,
        }
        if target_user.next_cursor:
            params.update({'cursor': target_user.next_cursor})

        cursor = tweepy.Cursor(self.api.followers, **params)

        try:
            for page in cursor.pages():
                self.last_request_date = datetime.datetime.now()
                self.save()
                settings.LOGGER.info("""Retrieved page with cursor %i
                    \n\tNext cursor: %i
                    \n\tPrevious cursor: %i
                """ % (target_user.next_cursor, cursor.iterator.next_cursor,
                       cursor.iterator.prev_cursor))

                new_twitter_users = []
                new_followers = []
                # guardamos cada follower recibido, sin duplicar en BD
                for tw_follower in page:
                    # creamos twitter_user a partir del follower si ya no existe en BD
                    twitter_user_id, is_new = self.create_twitter_user_obj(tw_follower)
                    if is_new:
                        new_twitter_users.append(twitter_user_id)
                        settings.LOGGER.info('New twitter user %s added to list' % twitter_user_id.__unicode__())
                    else:
                        follower = Follower(twitter_user=twitter_user_id, target_user=target_user)
                        follower_already_exists = Follower.objects.filter(
                            twitter_user=twitter_user_id, target_user=target_user).exists()
                        if follower_already_exists:
                            if skip_page_on_existing:
                                settings.LOGGER.info('Follower %s already exists, skipping page..' % follower.__unicode__())
                                break
                            else:
                                settings.LOGGER.info('Follower %s already exists' % follower.__unicode__())
                        else:
                            new_followers.append(follower)
                            settings.LOGGER.info('New follower %s added to list' % follower.__unicode__())

                before_saving = datetime.datetime.now()
                time.sleep(2)  # para que se note la diferencia por si guarda muy rapido los twitterusers
                TwitterUser.objects.bulk_create(new_twitter_users)
                # pillamos todos los ids de los nuevos twitter_user creados
                new_twitter_users_ids = TwitterUser.objects\
                    .filter(date_saved__gt=before_saving)\
                    .values_list('id', flat=True)

                for twitter_user_id in new_twitter_users_ids:
                    new_followers.append(
                        Follower(twitter_user_id=twitter_user_id, target_user=target_user))

                Follower.objects.bulk_create(new_followers)

                # actualizamos el next_cursor para el target user
                target_user.next_cursor = cursor.iterator.next_cursor
                target_user.save()

            settings.LOGGER.info('All followers from %s retrieved ok' % target_user.username)
        except tweepy.error.TweepError as ex:
            if hasattr(ex.response, 'status_code') and ex.response.status_code == 429:
                raise RateLimitedException(self)
            else:
                settings.LOGGER.exception('')
                time.sleep(7)
                raise ex

    def extract_hashtag_users(self, hashtag):
        self.connect_twitter_api()

        while True:
            results = self.api.search(
                q=hashtag.q,
                geocode=hashtag.geocode,
                lang=hashtag.lang,
                result_type=hashtag.result_type,
                max_id=hashtag.max_id,
                count=10,
            )

            self.last_request_date = datetime.datetime.now()
            self.save()
            settings.LOGGER.info('Retrieved 100 tweets for hashtag "%s" (max_id=%s)' %
                                 (hashtag.q, str(hashtag.max_id)))

            new_twitter_users = []
            new_hashtag_users = []

            for result in results:
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

            before_saving = datetime.datetime.now()
            time.sleep(2)  # para que se note la diferencia por si guarda muy rapido los twitterusers
            TwitterUser.objects.bulk_create(new_twitter_users)
            # pillamos todos los ids de los nuevos twitter_user creados
            new_twitter_users_ids = TwitterUser.objects\
                .filter(date_saved__gt=before_saving)\
                .values_list('id', flat=True)

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
        target_users_to_extract = TargetUser.objects.filter(projects__is_running=True).exclude(next_cursor=None)
        if target_users_to_extract.exists():
            target_user = target_users_to_extract.first()
            self.extract_followers(target_user, skip_page_on_existing=True)
        else:
            settings.LOGGER.info('All followers were already extracted from all target users for active projects')

    def extract_twitter_users_from_all_hashtags(self):
        hashtags_to_extract = Hashtag.objects.filter(projects__is_running=True, is_extracted=False)
        if hashtags_to_extract.exists():
            hashtag = hashtags_to_extract.first()
            self.extract_hashtag_users(hashtag)
        else:
            settings.LOGGER.info('All followers were already extracted from all target users for active projects')
                
    def is_available(self):
        """Si fue marcadado como rate limited se mira si pasaron más de 15 minutos.
        En ese caso se desmarca y se devielve True"""
        if self.is_rate_limited:
            try:
                seconds_lapsed = (datetime.datetime.now().replace(tzinfo=pytz.UTC) - self.last_request_date).seconds
            except Exception:
                seconds_lapsed = (datetime.datetime.now() - self.last_request_date).seconds
                
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

    twitter_users = models.ManyToManyField(TwitterUser, through='TwitterUserHasHashtag',
                                           related_name='hashtags', blank=True)

    def __unicode__(self):
        return self.q


class TwitterUserHasHashtag(models.Model):
    hashtag = models.ForeignKey(Hashtag)
    twitter_user = models.ForeignKey(TwitterUser)
    date_saved = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s %s' % (self.twitter_user.username, self.hashtag.q)


class TweetImg(models.Model):
    # def get_img_path(self, filename):
    #     if self.pk:
    #         fileName, fileExtension = os.path.splitext(filename)
    #         path = '%s/photos/cat_%s/photo_%s.jpg' % \
    #         (self.country.upper(), self.category.id, self.id)
    #     return prepend_env_folder(path)

    img = models.ImageField(upload_to='images', blank=True, null=True)
    is_using = models.BooleanField(default=True)
    project = models.ForeignKey(Project, null=False, related_name='tweet_imgs')

    def __unicode__(self):
        return '%s @ %s' % (self.img.path, self.project.name)