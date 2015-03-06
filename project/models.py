# -*- coding: utf-8 -*-
import os
import random
import re
import subprocess
from threading import Thread, Timer
import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from django.db import models, connection
from django.db.models import Count, Q
import feedparser
import psutil
import tweepy
from tweepy.error import TweepError
from core.scrapper.exceptions import *
from project.exceptions import *
from project.managers import TargetUserManager, TweetManager, ProjectManager, ExtractorManager, ProxiesGroupManager, \
    TwitterUserManager, McTweetManager, FeedItemManager, HashtagManager
from core.scrapper.utils import is_gte_than_days_ago, utc_now, is_lte_than_seconds_ago, naive_to_utc, \
    generate_random_secs_from_minute_interval, has_elapsed_secs_since_time_ago, str_interval_to_random_num, \
    format_source, check_internet_connection_works, mkdir_if_not_exists, is_lte_than_days_ago
from twitter_bots import settings
from twitter_bots.settings import set_logger


class Project(models.Model):
    name = models.CharField(max_length=100, null=False, blank=True)
    is_running = models.BooleanField(default=True)
    has_tracked_clicks = models.BooleanField(default=False)

    # RELATIONSHIPS
    target_users = models.ManyToManyField('TargetUser', related_name='projects', blank=True)
    hashtags = models.ManyToManyField('Hashtag', related_name='projects', blank=True)
    # tu_groups = models.ManyToManyField('TUGroup', related_name='projects', null=True, blank=True)
    # hashtag_groups = models.ManyToManyField('HashtagGroup', related_name='projects', null=True, blank=True)

    objects = ProjectManager()

    def __unicode__(self):
        return self.name

    def get_max_tweets_to_send_queue_length(self):
        """Saca el máximo tamaño que puede tener la cola de tweets pendientes de enviar para el proyecto"""
        return self.get_twitteable_bots().count() * settings.MAX_QUEUED_TWEETS_TO_SEND_PER_BOT

    def get_max_unmentioned_twitterusers(self):
        """Saca el máximo de twitterusers sin mencionar que puede tener el proyecto"""
        return self.get_max_tweets_to_send_queue_length() * settings.EXTRACTION_FACTOR

    def check_if_full_of_unmentioned_twitterusers(self):
        # contamos aquellos twitterusers cuyo idioma coincida con el del lenguaje de los mensajes y pagelinks
        # para el proyecto. Si está el idioma inglés o no hay idioma entonces cualquiera vale
        valid_langs = self.get_langs_using()
        if not valid_langs or 'en' in valid_langs:
            unmentioned_count = self.get_unmentioned_users().count()
        else:
            unmentioned_count = self.get_unmentioned_users().filter(language__in=valid_langs).count()

        if unmentioned_count >= self.get_max_unmentioned_twitterusers():
            raise ProjectFullOfUnmentionedTwitterusers(self, valid_langs, unmentioned_count)

    def get_langs_using(self):
        """Saca los lenguajes que se usan para el proyecto"""
        tweet_msgs_langs = [lang for lang in self.tweet_msgs.values_list('language', flat=True).distinct() if lang]
        pagelinks_langs = [lang for lang in self.pagelinks.values_list('language', flat=True).distinct() if lang]
        return list(set(list(tweet_msgs_langs) + list(pagelinks_langs)))

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

    def get_tweets_sent(self):
        return Tweet.objects.filter(project=self, sent_ok=True)

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
        return TwitterBot.objects.using_in_project(self).twitteable_regardless_of_proxy()

    def get_active_targetusers_ordered_by_extraction_date(self):
        project_targetusers = TargetUser.objects.for_project(self)
        if project_targetusers.exists():
            # sacamos targetusers activos ordenados por fecha de última extracción
            project_targetusers_active = project_targetusers\
                .available_to_extract()\
                .extra(select={'date_le_null': 'date_last_extraction IS NULL',})\
                .order_by('date_last_extraction', 'date_le_null')
            if not project_targetusers_active.exists():
                ProjectHasAllTargetusersExtracted(self)
            return project_targetusers_active
        else:
            ProjectHasNoTargetUsers(self)
            return project_targetusers

    def get_active_hashtags_ordered_by_extraction_date(self):
        project_hashtags = Hashtag.objects.for_project(self)
        if project_hashtags.exists():
            # sacamos targetusers activos ordenados por fecha de última extracción
            project_hashtags_active = project_hashtags\
                .available_to_extract()\
                .extra(select={'date_le_null': 'date_last_extraction IS NULL',})\
                .order_by('date_last_extraction', 'date_le_null')
            if not project_hashtags_active.exists():
                ProjectHasAllHashtagsExtracted(self)
            return project_hashtags_active
        else:
            ProjectHasNoHashtags(self)

    def extract_twitterusers(self):
        """Se extraen twitterusers desde los @s y #s asignados al proyecto

        Comienza extrayendo de todos los targetusers, luego hashtags, y cuando todos tengan fecha
        de última extracción, extraemos hashtag si el último fue targetuser y viceversa
        """

        def order_by_last_extraction_date(queryset):
            """De los targetusers o hashtags dados filtra por los que estén disponibles y los ordena poniendo
            primero los que se extrajeron hace más tiempo y los más recientemente extraídos al final"""
            return queryset\
                .extra(select={'date_le_null': 'date_last_extraction IS NULL',})\
                .order_by('date_last_extraction', 'date_le_null')

        def get_targetusers_available():
            if project_targetusers.exists():
                # sacamos targetusers activos ordenados por fecha de última extracción
                project_targetusers_available = project_targetusers.available_to_extract()
                if not project_targetusers_available.exists():
                    ProjectHasAllTargetusersExtracted(self)
                return project_targetusers_available
            else:
                ProjectHasNoTargetUsers(self)
                return project_targetusers
            
        def get_hashtags_available():
            if project_hashtags.exists():
                # sacamos targetusers activos ordenados por fecha de última extracción
                project_hashtags_available = project_hashtags.available_to_extract()
                if not project_hashtags_available.exists():
                    ProjectHasAllHashtagsExtracted(self)
                return project_hashtags_available
            else:
                ProjectHasNoHashtags(self)
                return project_hashtags

        # primero ordenamos por fecha de extracción y luego filtramos por los disponibles para extraer
        project_targetusers = order_by_last_extraction_date(TargetUser.objects.for_project(self))
        project_hashtags = order_by_last_extraction_date(Hashtag.objects.for_project(self))
        targetusers_available = get_targetusers_available()
        hashtags_available = get_hashtags_available()
        targetuser_to_extract = targetusers_available.first()
        hashtag_to_extract = hashtags_available.first()

        if targetuser_to_extract and hashtag_to_extract:
            last_targetuser_extracted = project_targetusers.last()
            last_hashtag_extracted = project_hashtags.last()

            last_targetuser_extraction_date = last_targetuser_extracted.date_last_extraction
            last_hashtag_extraction_date = last_hashtag_extracted.date_last_extraction

            if last_targetuser_extraction_date and last_hashtag_extraction_date:
                # si el último targetuser extraído fue después del último hashtag extraído,
                # entonces ahora le toca al hashtag y viceversa
                if last_targetuser_extraction_date > last_hashtag_extraction_date:
                    hashtag_to_extract.extract_twitterusers()
                else:
                    targetuser_to_extract.extract_twitterusers()
            elif not last_targetuser_extraction_date and not last_hashtag_extraction_date:
                # tiramos primero del targetuser en caso que no haya nada extraído todavía
                targetuser_to_extract.extract_twitterusers()
            elif last_targetuser_extraction_date:
                # si tenemos fecha para targetusers y no hashtag le toca al hashtag
                hashtag_to_extract.extract_twitterusers()
            elif last_hashtag_extraction_date:
                # viceversa si tenemos fecha para hashtags
                targetuser_to_extract.extract_twitterusers()
        elif not targetusers_available.exists() and not hashtags_available.exists():
            raise ProjectHasNoTwitterusersToExtract(self)
        elif targetusers_available.exists():
            targetuser_to_extract.extract_twitterusers()
        elif hashtags_available.exists():
            hashtag_to_extract.extract_twitterusers()

    def clear_unmentioned_twitterusers(self):
        """Elimina todos los twitterusers sin mencionar guardados para el proyecto"""
        unmentioned = TwitterUser.objects.unmentioned_on_project(self)
        if unmentioned.exists():
            count = unmentioned.count()
            unmentioned.delete()
            settings.LOGGER.info('All unmentioned twitterusers were deleted for project %s (%i)' % (self.name, count))
        else:
            settings.LOGGER.info('Project %s has no unmentioned twitterusers' % self.name)

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
    next_cursor = models.BigIntegerField(null=True, blank=True, default=0)
    followers_count = models.PositiveIntegerField(null=True, default=0)

    # fecha en la que se terminó de extraer
    date_extraction_end = models.DateTimeField(null=True, blank=True)

    # fecha en la que se extrajo una página por última vez
    date_last_extraction = models.DateTimeField(null=True, blank=True)

    # número de páginas consecutivas de las que no se extrayó un número suficiente de followers
    num_consecutive_pages_without_enough_new_twitterusers = models.PositiveIntegerField(null=True, default=0)

    is_active = models.BooleanField(default=True)
    is_suspended = models.BooleanField(default=False)

    # REL
    twitter_users = models.ManyToManyField('TwitterUser', through='Follower',
                                           related_name='target_users', blank=True)

    objects = TargetUserManager()

    def __unicode__(self):
        return self.username

    def get_followers_mentioned(self):
        return self.followers.filter(twitter_user__mentions__isnull=False)

    def mark_as_extracted(self):
        settings.LOGGER.info('All followers from %s retrieved ok' % self.username)
        self.next_cursor = None
        self.date_extraction_end = utc_now()
        self.save()

    def has_all_pages_extracted(self):
        return self.next_cursor is None

    def has_too_many_pages_without_enough_new_twitterusers(self):
        return self.num_consecutive_pages_without_enough_new_twitterusers >= \
               settings.TARGETUSER_EXTRACTION_MAX_CONSECUTIVE_PAGES_RETRIEVED_WITHOUT_ENOUGH_NEW_TWITTERUSERS

    def check_if_enough_new_twitterusers(self, new_twitterusers):
        """Mira si el número de followers tomados desde la página extraída es menor
        que el umbral establecido

        :param new_twitterusers - nuevos twitterusers sacados de la página tomada por el extractor
        """
        if len(new_twitterusers) < settings.TARGETUSER_EXTRACTION_MIN_NEW_TWITTERUSERS_PER_PAGE_EXPECTED:
            settings.LOGGER.warning('Not enough new twitterusers retrieved (%d) from targetuser: %s' %
                                    (len(new_twitterusers), self.__unicode__()))
            self.num_consecutive_pages_without_enough_new_twitterusers += 1
        else:
            self.num_consecutive_pages_without_enough_new_twitterusers = 0
        self.save()

    def get_projects(self):
        return Project.objects.filter(
            Q(tu_groups__target_users=self) |
            Q(target_users=self)
        ).distinct()

    def extract_twitterusers(self):
        """
        Extrae los twitterusers seguidores del targetuser
        """

        available_extractors = Extractor.objects.available(Extractor.FOLLOWER_MODE)
        if available_extractors.exists():
            for extractor in available_extractors:
                try:
                    extractor.extract_twitterusers_from_targetuser(self)
                except TweepError as e:
                    if 'Cannot connect to proxy' in e.reason:
                        settings.LOGGER.exception('Extractor %s can\'t connect to proxy %s' %
                                                      (extractor.twitter_bot.username,
                                                       extractor.twitter_bot.proxy_for_usage.__unicode__()))
                        # si no podemos conectar al proxy del extractor vamos al siguiente
                        continue
                    else:
                        raise e
                except RateLimitedException:
                    # si el extractor superó el ratio de peticiones pasamos al siguiente
                    continue
                except (ExtractorReachedMaxConsecutivePagesRetrievedPerTUser,
                        TargetUserExtractionCompleted,
                        TargetUserWasSuspended,
                        InternetConnectionError):
                    break

            time.sleep(random.randint(1, 5))
        else:
            NoAvaiableExtractors(Extractor.FOLLOWER_MODE)

    def check_if_extraction_completed(self, last_processed_page):
        """Comprueba si se teminó la extracción del target dada la última página que se le procesó"""

        # Damos como extraído el targetuser cuando se cumpla alguna de las condiciones:
        #   - El número de usuarios en la última página extraída es menor a la mitad
        #   - El cursor para la página siguiente es None
        #   - Se ha superado el número de páginas extraídas consecutivamente sin un número suficiente de followers
        if len(last_processed_page) < settings.TARGET_USER_PAGE_SIZE/2 \
                or self.has_all_pages_extracted() \
                or self.has_too_many_pages_without_enough_new_twitterusers():
            # dejamos de extraer ese target user
            raise TargetUserExtractionCompleted(self)


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

    def set_last_tweet_date_and_source(self, tw_user_from_api):
        if hasattr(tw_user_from_api, 'status'):
            if hasattr(tw_user_from_api.status, 'created_at'):
                self.last_tweet_date = naive_to_utc(tw_user_from_api.status.created_at)
            if hasattr(tw_user_from_api.status, 'source'):
                self.source = format_source(tw_user_from_api.status.source)
            else:
                self.source = TwitterUser.OTHERS
        else:
            self.source = TwitterUser.OTHERS


class Tweet(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)  # la fecha en la que se crea y se mete en la cola
    date_sent = models.DateTimeField(null=True, blank=True, db_index=True)
    sending = models.BooleanField(default=False, db_index=True)
    sent_ok = models.BooleanField(default=False, db_index=True)

    # RELATIONSHIPS
    tweet_msg = models.ForeignKey('TweetMsg', null=True, blank=True, on_delete=models.PROTECT)
    link = models.ForeignKey('Link', related_name='tweets', null=True, blank=True, on_delete=models.PROTECT)
    page_announced = models.ForeignKey('PageLink', related_name='tweets', null=True, blank=True, on_delete=models.PROTECT)
    bot_used = models.ForeignKey('core.TwitterBot', related_name='tweets', null=True, blank=True)
    mentioned_users = models.ManyToManyField('TwitterUser', related_name='mentions', null=True, blank=True)
    mentioned_bots = models.ManyToManyField('core.TwitterBot', related_name='mentions', null=True, blank=True)
    project = models.ForeignKey('Project', related_name='tweets', null=True, blank=True)
    tweet_img = models.ForeignKey('TweetImg', related_name='tweets', null=True, blank=True, on_delete=models.PROTECT)
    feed_item = models.ForeignKey('FeedItem', related_name='tweets', null=True, blank=True, on_delete=models.PROTECT)

    objects = TweetManager()

    def __unicode__(self):
        return self.compose() or '<< empty tweet >>'

    def compose(self, with_link=True):
        """with_link a False se usará para componer sin links a la hora de verificar mctweets
        en notificaciones del destinatario, donde se compararán sin link, ya que twitter pone otro"""

        compose_txt = ''

        mentions = self.mentioned_users.all() or self.mentioned_bots.all()
        m_txt = ''
        # solo se podrá consultar los usuarios mencionados si antes se guardó la instancia del tweet en BD
        for m in mentions:
            m_txt += '@%s ' % m.username
        compose_txt += m_txt

        if self.tweet_msg:
            compose_txt += self.tweet_msg.text

        if with_link and self.link:
            compose_txt += ' ' + self.link.url if self.link else ''

        if self.page_announced:
            # si ya tiene agregado mensaje o link le metemos espacio para luego el pagelink
            if self.tweet_msg or self.link:
                compose_txt += ' '
            compose_txt += self.page_announced.compose(with_link=with_link)

        if self.feed_item:
            if with_link:
                compose_txt += self.feed_item.__unicode__()
            else:
                compose_txt += self.feed_item.text

        return compose_txt

    def length(self):
        total_length = len(self.compose(with_link=False))

        if self.has_link():
            total_length += 1 + settings.TWEET_LINK_LENGTH
        if self.has_image():
            total_length += settings.TWEET_IMG_LENGTH

        return total_length

    def has_space(self):
        """Devuelve si el tweet no supera los 140 caracteres"""
        return self.length() < 140

    def exceeded_tweet_limit(self):
        return self.length() > 140

    def has_image(self):
        return self.tweet_img != None or (self.page_announced and self.page_announced.image != None)
    has_image.boolean = True

    def has_link(self):
        return self.link \
               or (self.page_announced and self.page_announced.page_link)\
               or (self.feed_item and self.feed_item.link)

    def get_image(self):
        return self.tweet_img or (self.page_announced.image if self.page_announced else None)

    def is_available(self):
        return not self.sending and not self.sent_ok

    def add_bot_to_mention(self):
        """Añade sobre el tweet un bot que se pueda mencionar"""

        from core.models import TwitterBot

        bot_used_group = self.bot_used.get_group()

        mentionable_bots = self.bot_used.get_rest_of_bots_under_same_group()
        if mentionable_bots.exists():
            # los ordenamos poniendo primero al que le llegaron menos mctweets desde este bot remitente (self.bot_used)
            mentionable_bots = mentionable_bots.annotate__mctweets_received_count()\
                .order_by('mctweets_received_count')

            # comprobamos si el que le llegaron menos mctweets pasó el timewindow para poder ser mencionado de nuevo
            for bot in mentionable_bots:
                if not bot.mentions.exists():
                    # si el bot no fue mencionado nunca, entonces se añade
                    self.mentioned_bots.add(bot)
                    break
                else:
                    latest_mctweet_to_bot = bot.mentions.latest('date_created')
                    timewindow = generate_random_secs_from_minute_interval(
                        bot_used_group.mctweet_to_same_bot_time_window)

                    timewindow_passed = has_elapsed_secs_since_time_ago(
                        latest_mctweet_to_bot.date_created, timewindow)
                    if timewindow_passed:
                        self.mentioned_bots.add(bot)
                        break
                # else:
                #     settings.LOGGER.debug('Bot %s can\'t be mentioned because not passed '
                #                           'mctweet_to_same_bot_time_window (%s min)' %
                #                           (bot.username, bot_used_group.mctweet_to_same_bot_time_window))

            if not self.mentioned_bots.exists():
                raise BotWithoutBotsToMention(self.bot_used)
        else:
            raise BotWithoutBotsToMention(self.bot_used)

    def add_twitterusers_to_mention(self):
        if self.tweet_msg:
            language = self.tweet_msg.language
        else:
            language = None

        unmentioned_for_tweet_to_send = TwitterUser.objects.get_unmentioned_on_project(
                    self.project,
                    limit=self.bot_used.get_group().max_num_mentions_per_tweet,
                    language=language
                )

        if unmentioned_for_tweet_to_send:
            for unmentioned in unmentioned_for_tweet_to_send:
                if self.length() + len(unmentioned.username) + 2 <= 140:
                    self.mentioned_users.add(unmentioned)
                else:
                    break

            settings.LOGGER.info('Queued [proj: %s | bot: %s] >> %s' %
                                 (self.project.__unicode__(), self.bot_used.__unicode__(), self.compose()))
            # break
        else:
            raise ProjectWithoutUnmentionedTwitterusers(self.project)

    def add_tweet_msg(self, project):
        tweet_message = project.tweet_msgs.order_by('?').first()
        if self.length() + len(tweet_message.text) <= 140:
            self.tweet_msg = tweet_message
            self.save()
        else:
            settings.LOGGER.warning('Tweet %s is too long to add custom message %s' %
                                    (self, tweet_message))

    def add_page_announced(self, project):
        active_pagelinks = project.pagelinks.filter(is_active=True)
        if active_pagelinks.exists():
            page_announced = active_pagelinks.order_by('?').first()
            if self.length() + page_announced.length() <= 140:
                self.page_announced = page_announced
                self.save()
            else:
                settings.LOGGER.warning('Tweet %s is too long to add page link %s' %
                                        (self, page_announced))
        else:
            raise Exception('Bot %s tried to build tweet for project %s but it has no pagelinks. '
                            'Try one of two: add at least one pagelink or disable "has_page_links" '
                            'on his group: %s' %
                            (self.bot_used.username, project.__unicode__(), self.bot_used.get_group().name))

    def add_image(self, project):
        if project.tweet_imgs.exists():
            if self.length() + 23 <= 140:
                self.tweet_img = project.tweet_imgs.order_by('?')[0]
                self.save()
            else:
                settings.LOGGER.warning('Tweet %s is too long to add image' %
                                        (self))
        else:
            settings.LOGGER.warning('Project %s has no images' % project.__unicode__())

    def add_link(self, project):
        link = project.links.filter(is_active=True).order_by('?').first()
        if self.length() + len(link.url) + 1 <= 140:
            self.link = link
            self.save()
        else:
            settings.LOGGER.warning('Tweet %s is too long to add link %s' %
                                    (self, link))


    def send_with_casperjs(self):
        """
        /path/to/phantomjs_linux_bin
            --proxy=173.234.58.20:8800
            --cookies-file=/path/to/cookies/1805_Charlie_Grillo.txt
            --ssl-protocol=any
        """
        def check_if_errors():
            errors = o['errors']
            if 'pageload_timeout_expired' in errors:
                raise PageloadTimeoutExceeded(settings.PAGE_LOAD_TIMEOUT_SENDING_TWEETS)
            elif 'casperjs_error' in errors:
                raise CasperJSError(sender)
            elif 'not_logged_in' in errors:
                raise BotNotLoggedIn(sender)
            elif 'tweet_already_sent' in errors:
                raise TweetAlreadySent(self)
            elif 'account_suspended' in errors:
                raise TwitterAccountSuspended(sender)
            elif 'internet_connection_error' in errors:
                raise InternetConnectionError
            elif 'unknown_error' in errors:
                raise UnknownErrorSendingTweet(self)

        sender = self.bot_used
        tweet_dirname = '%d_%s' % (self.pk, self.print_type())
        screenshots_dir = os.path.join(sender.get_screenshots_dir(), tweet_dirname)
        mkdir_if_not_exists(screenshots_dir)

        command = [
            settings.CASPERJS_BIN_PATH,
            os.path.join(settings.CASPERJS_SCRIPTS_PATH, 'twitter_send_tweet.js'),
            '--proxy=%s' % sender.proxy_for_usage.proxy,
            '--cookies-file=%s' % sender.get_cookies_file_for_casperjs(),
            '--ssl-protocol=any',
            '--useragent=%s' % sender.user_agent,
            '--screenshots=%s/' % screenshots_dir,
            '--take-screenshots=%s' % settings.TAKE_SCREENSHOTS,
            '--pageload-timeout=%i' % settings.PAGE_LOAD_TIMEOUT_SENDING_TWEETS,
            '--tweetmsg=%s' % self.compose().encode('utf-8')
        ]

        if self.tweet_img:
            command.append('--tweetimg=%s' % self.tweet_img.img.path)

        # esperamos a que la cpu se alivie
        while psutil.cpu_percent() > 90.0:
            time.sleep(0.5)

        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        timer = Timer(settings.CASPERJS_PROCESS_TIMEOUT, proc.kill)
        timer.start()
        stdout, stderr = proc.communicate()
        if timer.is_alive():
            timer.cancel()
            try:
                o = simplejson.loads(stdout.strip('\n'))
                check_if_errors()
            except simplejson.JSONDecodeError as e:
                if stdout:
                    if re.match(r".*Wait timeout of .*ms expired.*", stdout):
                        return CasperJSWaitTimeoutExceeded(sender)
                    else:
                        settings.LOGGER.error('Error parsing json stdout: %s' % stdout)
                else:
                    settings.LOGGER.error('No stdout returned (bot %s)' % sender.username)
                raise e
        else:
            # si el timer agota la espera, es decir, se mato casperjs
            raise CasperJSProcessTimeoutError(sender)


    def send_with_webdriver(self):
        """Deprecated"""
        def check_if_sent_ok():
            # si aún aparece el diálogo de twitear es que no se envió ok
            if scr.check_visibility('#global-tweet-dialog'):

                # miramos si sale mensajito de 'you already sent this tweet'
                if scr.check_visibility('#message-drawer .message-text'):
                    raise TweetAlreadySent(self)
                else:
                    raise FailureSendingTweet(self)

        scr = self.bot_used.scrapper
        try:
            screenshots_dir_name = '%d_%s' % (self.pk, self.print_type())
            scr.set_screenshots_dir(screenshots_dir_name)
            scr.open_browser()
            scr.login()
            scr.delay.seconds(5)

            scr.click('#global-new-tweet-button')

            scr.send_keys(self.compose())

            if self.has_image():
                el = self.browser.find_element_by_xpath("//*[@id=\"global-tweet-dialog-dialog\"]"
                                                        "/div[2]/div[4]/form/div[2]/div[1]/div[1]/div/label/input")
                el.send_keys(self.get_image().img.path)

            scr.click('#global-tweet-dialog-dialog .tweet-button button')
            scr.delay.seconds(5)
            check_if_sent_ok()
            scr.delay.seconds(7)
        except TwitterEmailNotConfirmed:
            # si al intentar enviar el tweet el usuario no estaba realmente confirmado eliminamos su tweet
            scr.logger.warning('Tweet %i will be deleted' % self.pk)
            self.delete()
        except (TweetAlreadySent,
                ProxyUrlRequestError,
                ConnectionError,
                NoAvailableProxiesToAssignBotsForUse,
                FailureSendingTweet):
            pass
        finally:
            scr.close_browser()

    def send_with_burst(self):
        """Envía el tweet junto a una ráfaga de tweets a enviar por el mismo bot"""

        # class SendTweetThread(Thread):
        #
        #     def __init__(self, tweet):
        #         self.tweet = tweet
        #         self.output = None
        #         super(SendTweetThread, self).__init__()
        #
        #     def run(self):
        #         self.tweet.send()
        #         try:
        #             self.sTitle = str(audio["TIT2"])
        #         except KeyError:
        #             self.sTitle = os.path.basename(self.fileName)
        #
        #         self.sTitle = replace_all(self.sTitle) #remove special chars
        #
        # # miramos qué rafaga tiene asignada el grupo del que envía este tweet. Si es > 1 entonces
        # # enviaremos más tweets
        # burst_size = self.bot_used.get_group().tweets_per_burst
        # for i in xrange(burst_size):
        #     settings.LOGGER.info('Bot %s sending tweet %i [%s] (%i/%i in burst): >> %s' %
        #                          (i+1,
        #                           burst_size,
        #                           self.bot_used.__unicode__(),
        #                           self.pk,
        #                           self.print_type(),
        #                           self.compose()))
        pass

    def send(self):
        if not settings.LOGGER:
            set_logger('tweet_sender')

        sender = self.bot_used

        settings.LOGGER.info('%s sending tweet %i [%s]: >> %s' %
                             (sender.__unicode__(),
                              self.pk,
                              self.print_type(),
                              self.compose()))

        # intentamos enviar con casperjs. si no es posible logueamos usando webdriver,
        # comprobando cuenta suspendida etc
        try:
            self.send_with_casperjs()
            pass
        except BotNotLoggedIn:
            sender.login_twitter_with_webdriver()
        except (TweetAlreadySent,
                TwitterAccountSuspended,
                PageloadTimeoutExceeded,
                simplejson.JSONDecodeError,
                CasperJSWaitTimeoutExceeded,
                CasperJSProcessTimeoutError,
                UnknownErrorSendingTweet):
            raise FailureSendingTweet(self)
        except Exception as e:
             settings.LOGGER.exception('Error on bot %s (%s) sending tweet with id=%i)' %
                                      (self.bot_used.username, self.bot_used.real_name, self.pk))
             raise e
        else:
            self.sent_ok = True
            self.date_sent = utc_now()
            self.save()
            settings.LOGGER.info('%s sent ok tweet %s [%s] with casperJS'
                                 % (sender.username, self.pk, self.print_type()))
        finally:
            # si el tweet sigue en BD se desmarca como enviando
            if Tweet.objects.filter(pk=self.pk).exists():
                self.sending = False
                self.save()

            # cerramos conexión con BD
            connection.close()

    def enough_time_passed_since_last(self):
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
            random_seconds_ago = generate_random_secs_from_minute_interval(self.bot_used.get_group().time_between_tweets)
            if is_lte_than_seconds_ago(last_tweet_sent.date_sent, random_seconds_ago):
                return True
            else:
                return False

    def log_reason_to_not_send(self, reason):

        if self.has_twitterusers_mentions():
            do = 'mention twitter users'
        elif self.has_twitterbots_mentions():
            do = 'mention twitter bots'
        else:
            do = 'tweet'

        settings.LOGGER.debug('Bot %s can\'t %s because %s' % (self.bot_used.username, do, reason))

    def check_if_can_be_sent(self):
        """Comprueba si el tweet puede enviarse o no"""

        self._check_if_errors_on_construction()

        sender_bot = self.bot_used

        if sender_bot.has_to_follow_people():
            raise SenderBotHasToFollowPeople(sender_bot)

        # if not sender_bot.has_enough_time_passed_since_his_last_tweet():
        #     raise BotHasNotEnoughTimePassedToTweetAgain(sender_bot)

        if not self.has_enough_ftweets_sent():
            raise MuTweetHasNotSentFTweetsEnough(self)

        if self.has_twitterusers_mentions() \
                and sender_bot.has_reached_consecutive_twitteruser_mentions():
            raise BotHasReachedConsecutiveTUMentions(sender_bot)

    def get_ftweets_count_to_send_before(self):
        """Devuelve cuántos ftweets hay que enviar antes del tumention"""

        if self.has_twitterusers_mentions():
            try:
                return self.ftweets_num.number
            except ObjectDoesNotExist:
                ftweets_number = str_interval_to_random_num(
                    self.bot_used.get_group().feedtweets_per_twitteruser_mention)

                FTweetsNumPerTuMention.objects.create(number=ftweets_number, tu_mention=self)

                return self.ftweets_num.number
        else:
            raise MethodOnlyAppliesToTuMentions

    def _check_if_errors_on_construction(self):
        if not self.is_well_constructed():
            raise TweetConstructionError(self)

    def has_twitterusers_mentions(self):
        return self.mentioned_users.all().exists()

    def has_twitterbots_mentions(self):
        return self.mentioned_bots.exists()

    def has_mentions(self):
        return self.has_twitterusers_mentions() or self.has_twitterbots_mentions()

    def check_if_can_be_verified(self):
        """Comprueba si el tweet puede ser verificado por bot destino"""

        if self.has_twitterbots_mentions():
            self._check_if_errors_on_construction()
            if not self.date_sent:
                raise SentOkMcTweetWithoutDateSent(self)
            else:
                # comprobamos que el bot destino no esté siendo usando
                destination_bot = self.mentioned_bots.first()
                if destination_bot.is_already_being_used():
                    raise DestinationBotIsBeingUsed(self)
                elif destination_bot.is_dead:
                    raise DestinationBotIsDead(self)
                else:
                    # comprobamos que si ya se ha pasado el time window desde que el bot que lanza el tweet
                    # fue detectado que no puede mencionar
                    verif_time_window = self.bot_used.get_group().destination_bot_checking_time_window
                    verif_time_window_is_passed = has_elapsed_secs_since_time_ago(
                        self.date_sent,
                        generate_random_secs_from_minute_interval(verif_time_window)
                    )
                    if not verif_time_window_is_passed:
                        raise VerificationTimeWindowNotPassed(self)
        else:
            raise MethodOnlyAppliesToTbMentions

    def has_enough_ftweets_sent(self):
        return self.get_ftweets_sent().count() >= self.get_ftweets_count_to_send_before()

    def get_or_create_ftweet_to_send(self):
        """Se busca un ftweet ya creado y que no se haya enviado. Si existe se crea"""

        settings.LOGGER.debug('getting ftweet_to_send..')
        ftweet_to_send = self.tweets_from_feed.filter(tweet__sent_ok=False)
        settings.LOGGER.debug('..ok')

        if ftweet_to_send.exists():
            if ftweet_to_send.count() > 1:
                settings.LOGGER.warning('There were found multiple ftweets pending to send from '
                                      'bot %s and will be deleted' % self.username)
                self.clear_not_sent_ok_ftweets()
                ftweet_to_send = self.bot_used.make_ftweet_to_send()
            else:
                # si ya había alguno creado se envía
                ftweet_to_send = ftweet_to_send.first().tweet
        else:
            ftweet_to_send = self.bot_used.make_ftweet_to_send()

        # si el ftweet no tiene asociado el registro tff lo crea
        TweetFromFeed.objects.get_or_create(tweet=ftweet_to_send, tu_mention=self)

        return ftweet_to_send

    def get_ftweets_sent(self):
        """Devuelve cuantos ftweets se enviaron para el tweet"""
        return self.tweets_from_feed.filter(tweet__sent_ok=True)

    def print_type(self):
        if self.is_mutweet():
            return 'TU_MENTION'
        elif self.is_mctweet():
            return 'MC_TWEET'
        elif self.is_ftweet():
            return 'F_TWEET'
        else:
            return '???'

    def is_mutweet(self):
        return self.project and self.has_twitterusers_mentions()

    def is_mctweet(self):
        return not self.project and self.has_twitterbots_mentions()

    def is_ftweet(self):
        return not self.project and self.feed_item and not self.mentioned_bots.exists()

    def is_well_constructed(self):
        def content_ok_mutweet():
            """Dice si el tweet tiene el contenido ok según se indicó en las propiedades
            del grupo para el bot remitente"""
            sender_group = self.bot_used.get_group()
            wrong_msg = sender_group.has_tweet_msg and not self.tweet_msg
            wrong_link = sender_group.has_link and not self.link
            wrong_img = sender_group.has_tweet_img and not self.tweet_img
            wrong_page_announced = sender_group.has_page_announced and not self.page_announced

            return not wrong_msg and not wrong_link and not wrong_img and not wrong_page_announced

        def content_ok_mctweet():
            return content_ok_ftweet()

        def content_ok_ftweet():
            return not self.tweet_msg and not self.link and not self.tweet_img and not self.page_announced

        if self.is_mutweet():
            return content_ok_mutweet()
        elif self.is_mctweet():
            return content_ok_mctweet()
        elif self.is_ftweet():
            return content_ok_ftweet()
        else:
            return False

    def process(self, pool=None):
        """Procesa el tweet de la cola para ver qué tarea tenemos que enviar al pool de threads"""

        def log_task_adding(task_name):
            settings.LOGGER.debug('Adding task [%s] (total unfinished: %d)' % (task_name, pool.tasks.unfinished_tasks))

        try:
            self.check_if_can_be_sent()
            self.sending = True
            self.save()
            if pool:
                log_task_adding('SEND MU_TWEET')
                pool.add_task(self.send)
            else:
                self.send()
        except (TweetConstructionError,
                BotIsAlreadyBeingUsed,
                BotHasNotEnoughTimePassedToTweetAgain):
            pass

        except BotHasReachedConsecutiveTUMentions as e:
            mctweet_sender_bot = e.bot
            mctweet = mctweet_sender_bot.get_or_create_mctweet()

            if mctweet.sent_ok:
                try:
                    mctweet.check_if_can_be_verified()
                    mctweet.tweet_checking_mention.destination_bot_is_checking_mention = True
                    mctweet.tweet_checking_mention.save()
                    mentioned_bot = mctweet.mentioned_bots.first()

                    if pool:
                        log_task_adding('VERIFY MC_TWEET')
                        pool.add_task(mentioned_bot.verify_mctweet_if_received_ok, mctweet)
                    else:
                        mentioned_bot.verify_mctweet_if_received_ok(mctweet)
                except (TweetConstructionError,
                        DestinationBotIsBeingUsed,
                        DestinationBotIsDead,
                        VerificationTimeWindowNotPassed,
                        SentOkMcTweetWithoutDateSent):
                    pass
            else:
                try:
                    mctweet_sender_bot.check_if_can_send_mctweet()
                    mctweet.sending = True
                    mctweet.save()
                    if pool:
                        log_task_adding('SEND MC_TWEET')
                        pool.add_task(mctweet.send)
                    else:
                        mctweet.send()
                except LastMctweetFailedTimeWindowNotPassed:
                    pass

        except MuTweetHasNotSentFTweetsEnough as e:
            ftweet = e.mutweet.get_or_create_ftweet_to_send()
            ftweet.sending = True
            ftweet.save()
            if pool:
                log_task_adding('SEND F_TWEET')
                pool.add_task(ftweet.send)
            else:
                try:
                    ftweet.send()
                except FailureSendingTweet:
                    pass

        except SenderBotHasToFollowPeople as e:
            sender_bot = e.sender_bot
            sender_bot.is_following = True
            sender_bot.save()
            # marcamos los twitterusers a seguir por el bot
            sender_bot.mark_twitterusers_to_follow_at_once()
            if pool:
                log_task_adding('FOLLOW PEOPLE')
                pool.add_task(sender_bot.follow_twitterusers)
            else:
                try:
                    sender_bot.follow_twitterusers()
                except FollowTwitterUsersError:
                    pass

        except FailureSendingTweet:
            pass
        except Exception as e:
            settings.LOGGER.exception('Error getting tumention from queue for bot %s: %s' %
                                  (self.bot_used.username, self.compose()))
            raise e


class TweetCheckingMention(models.Model):
    tweet = models.OneToOneField('Tweet', related_name='tweet_checking_mention', null=False, blank=False)
    destination_bot_is_checking_mention = models.BooleanField(default=False)
    destination_bot_checked_mention = models.BooleanField(default=False)
    destination_bot_checked_mention_date = models.DateTimeField(null=True, blank=True)
    mentioning_works = models.BooleanField(default=False)

    objects = McTweetManager()

    class Meta:
        verbose_name_plural = 'Tweets checking mention'


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

    is_suspended = models.BooleanField(default=False)
    date_suspended = models.DateTimeField(null=True, blank=True)

    FOLLOWER_MODE = 1
    HASHTAG_MODE = 2
    BOTH = 3
    MODES = (
        (FOLLOWER_MODE, 'follower mode'),
        (HASHTAG_MODE, 'hashtag mode'),
        (BOTH, 'both'),
    )
    mode = models.PositiveIntegerField(null=False, choices=MODES)

    objects = ExtractorManager()

    def __unicode__(self):
        return self.twitter_bot.username

    def connect_twitter_api(self):
        """
            Antes de conectar comprobamos que el proxy no esté anticuado
        """

        self.twitter_bot.check_proxy_ok()

        auth = tweepy.OAuthHandler(self.consumer_key, self.consumer_secret)
        auth.set_access_token(self.access_token, self.access_token_secret)
        self.api = tweepy.API(auth, proxy=self.twitter_bot.proxy_for_usage.proxy)

    def get(self, uri):
        # url = 'https://api.twitter.com/1.1/followers/list.json?cursor=2&screen_name=candycrush&count=5000'
        resp = self.api.get(self.BASE_URL + uri)
        return simplejson.loads(resp.content)

    def get_user_info(self, username):
        return self.get('users/show.json?screen_name=%s' % username)

    def log_being_used(self):
        settings.LOGGER.info('### Using extractor %s behind proxy %s ###' %
                             (self.twitter_bot.username,
                              self.twitter_bot.proxy_for_usage.__unicode__()))

    # def format_datetime(self, twitter_datetime_str):
    #     if not twitter_datetime_str:
    #         return None
    #     else:
    #         return datetime.datetime.strptime(twitter_datetime_str, '%a %b %d %H:%M:%S +0000 %Y')

    def update_target_user_data(self, target_user):
        tw_user = self.api.get_user(screen_name=target_user.username)
        target_user.followers_count = tw_user.followers_count
        target_user.save()

    def create_new_twitter_user_obj(self, tw_user_from_api):
        """Crea un nuevo objeto twitteruser a partir de tw_user_from_api. no se guarda en BD todavía"""
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
        twitter_user.set_last_tweet_date_and_source(tw_user_from_api)

        return twitter_user

    def is_available(self):
        """Si fue marcadado como rate limited se mira si pasaron más de 15 minutos.
        En ese caso se desmarca y se devielve True"""
        if self.is_suspended:
            return False
        elif self.is_rate_limited:
            minutes_window = self.minutes_window or settings.DEFAULT_RATELIMITED_TIMEWINDOW
            time_window_passed = has_elapsed_secs_since_time_ago(self.last_request_date, self.minutes_window * 60)
            if time_window_passed:
                self.is_rate_limited = False
                self.save()
                return True
            else:
                return False
        else:
            return True

    def mark_as_suspended(self):
        """Se marca como suspendido el extractor, no el bot en sí"""
        self.is_suspended = True
        self.date_suspended = utc_now()
        self.save()
        settings.LOGGER.warning('Extractor %s has marked as suspended' % self.__unicode__())

    def extract_twitterusers_from_targetuser(self, target_user):
        """Pone al extractor a extraer twitterusers desde un targetuser dado"""

        @transaction.atomic
        def process_page(page):

            def process_new_tw_user(tw_user):
                # creamos twitter_user a partir del follower dado por la api
                twitter_user = self.create_new_twitter_user_obj(tw_user)
                twitteruser_name = twitter_user.__unicode__()

                if twitter_user.is_active():
                    new_twitter_users.append(twitter_user)
                    settings.LOGGER.info('%s%s added' % (pre_msg, twitteruser_name))
                else:
                    settings.LOGGER.info('%s%s inactive. LTD: %s, CD: %s' %
                                         (pre_msg, twitteruser_name, twitter_user.last_tweet_date, twitter_user.created_date))

            self.last_request_date = utc_now()
            self.save()
            settings.LOGGER.info("""%s-- Retrieved follower page with cursor %i
                \n\tNext cursor: %i
                \n\tPrevious cursor: %i
            """ % (pre_msg, target_user.next_cursor, cursor.iterator.next_cursor,
                   cursor.iterator.prev_cursor))

            # quitamos los twitterusers que ya estuvieran guardados y
            # guardamos cada follower recibido, sin duplicar en BD
            existing_twitterusers_ids = TwitterUser.objects\
                .filter(twitter_id__in=page.ids()).values_list('twitter_id', flat=True)

            new_twitter_users = []

            for tw_user in page:
                if tw_user.id not in existing_twitterusers_ids:
                    process_new_tw_user(tw_user)

            if new_twitter_users:
                # metemos los nuevos twitter users y followers en BD
                before_saving = utc_now()
                time.sleep(2)  # para que se note la diferencia por si guarda muy rapido los twitterusers
                TwitterUser.objects.bulk_create(new_twitter_users)
                settings.LOGGER.info('%s-- %i new twitterusers saved in DB--' % (pre_msg, len(new_twitter_users)))

                # pillamos todos los ids de los nuevos twitter_user creados
                new_twitter_users_ids = TwitterUser.objects\
                    .filter(date_saved__gt=before_saving)\
                    .values_list('id', flat=True)
                new_followers = []
                for new_twuser_id in new_twitter_users_ids:
                    new_followers.append(Follower(twitter_user_id=new_twuser_id, target_user=target_user))
                Follower.objects.bulk_create(new_followers)
            else:
                 settings.LOGGER.warning('%s-- no new twitterusers to save in DB --' % pre_msg)

            return new_twitter_users

        try:
            self.connect_twitter_api()
            self.log_being_used()
            self.update_target_user_data(target_user)
            pre_msg = '[TargetUser: %s] >> ' % target_user.username

            settings.LOGGER.info('%s-- Extracting followers (project(s) using: %s) --' %
                                 (pre_msg, Project.objects.get_names_list(target_user.get_projects())))

            params = {
                'screen_name': target_user.username,
                'count': settings.TARGET_USER_PAGE_SIZE,
            }
            if target_user.next_cursor:
                params.update({'cursor': target_user.next_cursor})

            cursor = tweepy.Cursor(self.api.followers, **params)

            num_pages_retrieved = 0

            for page in cursor.pages():
                new_twitter_users, new_followers = process_page(page)

                target_user.date_last_extraction = utc_now()
                target_user.save()

                target_user.check_if_enough_new_twitterusers(new_twitter_users)
                target_user.check_if_extraction_completed(page)

                # actualizamos el next_cursor para el target user
                target_user.next_cursor = cursor.iterator.next_cursor
                target_user.save()

                num_pages_retrieved += 1
                if num_pages_retrieved == settings.MAX_CONSECUTIVE_PAGES_RETRIEVED_PER_TARGET_USER_EXTRACTION:
                    raise ExtractorReachedMaxConsecutivePagesRetrievedPerTUser(self)
        except tweepy.error.TweepError as e:
            self.handle_tweeperror(e, targetuser=target_user)

    def extract_twitterusers_from_hashtag(self, hashtag):
        """Pone al extractor a extraer twitterusers que hayan tuiteado con el hashtag dado"""

        def process_page():

            def print_current_page_retrieved():
                return '%s/%s' % (num_pages_retrieved+1, hashtag.get_max_consecutive_pages_retrieved_per_extraction())

            def check_if_limits_reached():
                def check_oldest_tweet_and_max_users_limit():
                    if older_limit_reached:
                        raise HashtagOlderTweetDateLimitReached(hashtag, oldest_tweet_date)
                    elif max_user_limit_reached:
                        raise HashtagMaxUsersCountReached(hashtag)

                # enough new twitter users limit
                hashtag.check_if_enough_new_twitterusers(new_twitter_users)

                # oldest_tweet and max_users limits
                oldest_tweet = page[-1]
                oldest_tweet_date = naive_to_utc(oldest_tweet.created_at)
                if hashtag.is_in_first_round():
                    older_limit_reached = is_lte_than_seconds_ago(
                        oldest_tweet_date,
                        settings.FIRST_HASHTAG_ROUND_MAX_MINUTES_AGO_FOR_OLDER_TWEET * 60
                    )
                    max_user_limit_reached = hashtag.current_round_user_count >= settings.FIRST_HASHTAG_ROUND_MAX_USER_COUNT
                    check_oldest_tweet_and_max_users_limit()
                else:
                    older_limit_reached = oldest_tweet_date <= hashtag.current_round_oldest_tweet_limit
                    max_user_limit_reached = hashtag.current_round_user_count >= settings.PER_HASHTAG_ROUND_MAX_USER_COUNT
                    check_oldest_tweet_and_max_users_limit()

            def check_if_results():
                # comprobamos que recibimos tweets de la API, por si el max_id hace referencia a un tweet
                # que ahora no existe porque se eliminó entre la extracción anterior y esta
                if not page:
                    raise HashtagExtractionWithoutResults(hashtag)

            def save_new_twitterusers(page):
                """Busca en la página obtenida qué usuarios son nuevos y los guarda"""

                @transaction.atomic
                def save_new_twusers_collected():
                    if new_twitter_users:
                        before_saving = utc_now()
                        time.sleep(2)  # para que se note la diferencia por si guarda muy rapido los twitterusers
                        TwitterUser.objects.bulk_create(new_twitter_users)
                        settings.LOGGER.info('%s%i new twitterusers saved in DB' % (pre_msg, len(new_twitter_users)))

                        # pillamos todos los ids de los nuevos twitter_user creados para crear sus relaciones con el hashtag
                        new_twitter_users_ids = TwitterUser.objects\
                            .filter(date_saved__gt=before_saving)\
                            .values_list('id', flat=True)
                        new_hashtags_twitterusers = []
                        for twitter_user_id in new_twitter_users_ids:
                            new_hashtags_twitterusers.append(
                                TwitterUserHasHashtag(twitter_user_id=twitter_user_id, hashtag=hashtag)
                            )
                        TwitterUserHasHashtag.objects.bulk_create(new_hashtags_twitterusers)
                    else:
                        settings.LOGGER.warning('%s no new twitterusers to save in DB' % pre_msg)

                def update_extraction_data():
                    # actualizamos para poder luego seguir por la siguiente página (cuando proceda, según límite de páginas por extracción)
                    if hashtag.round_just_begun():
                        hashtag.current_round_user_count = len(new_twitter_users)
                        hashtag.next_round_oldest_tweet_limit = newest_tweet_date
                    else:
                        hashtag.current_round_user_count += len(new_twitter_users)

                    oldest_tweet = page[-1]
                    hashtag.max_id = oldest_tweet.id
                    hashtag.date_last_extraction = utc_now()
                    hashtag.save()

                def process_new_tw_user(result):
                    twitter_user = self.create_new_twitter_user_obj(result.user)

                    # la fecha del último tweet siempre será la del recibido en esta página
                    twitter_user.last_tweet_date = naive_to_utc(result.created_at)

                    twitteruser_name = twitter_user.__unicode__()

                    new_twitter_users.append(twitter_user)
                    settings.LOGGER.debug('%s\t%s added' % (pre_msg, twitteruser_name))
                    twitterusers_ids_already_processed_on_page.append(result.user.id)

                def collect_new_twusers():
                    check_if_results()

                    settings.LOGGER.info('%sScanning page %s (max_id=%s) with %i tweets..' %
                                         (pre_msg, print_current_page_retrieved(), str(hashtag.max_id), len(page)))

                    page_twitterusers_ids = list(set([tweet.user.id for tweet in page]))
                    existing_on_db_twitterusers_ids = TwitterUser.objects\
                        .filter(twitter_id__in=page_twitterusers_ids).values_list('twitter_id', flat=True)

                    # procesamos cada tweet recibido por la API
                    for result in page:
                        # vemos que no se ha procesado antes (pueden haber varios twitterusers en una misma página)
                        if result.user.id not in twitterusers_ids_already_processed_on_page \
                                and result.user.id not in existing_on_db_twitterusers_ids:
                            process_new_tw_user(result)

                collect_new_twusers()
                save_new_twusers_collected()
                update_extraction_data()

                newest_tweet_date = naive_to_utc(page[0].created_at)
                oldest_tweet_date = naive_to_utc(page[-1].created_at)
                settings.LOGGER.info('%sPage %s processed (dates %s - %s)\n' %
                                     (pre_msg, print_current_page_retrieved(),
                                      datetime_to_str(newest_tweet_date), datetime_to_str(oldest_tweet_date)))

            page = self.api.search(
                q=hashtag.q,
                geocode=hashtag.geocode,
                lang=hashtag.lang,
                result_type=hashtag.result_type,
                max_id=hashtag.max_id,
                count=settings.HASHTAG_PAGE_SIZE,
            )

            # guardamos la fecha de esta última petición en el extractor
            self.last_request_date = utc_now()
            self.save()

            # aquí meteremos los usuarios nuevos a guardar en BD
            new_twitter_users = []
            # para no tener que volver a procesar un twitteruser ya tratado en la misma página
            twitterusers_ids_already_processed_on_page = []
            save_new_twitterusers(page)
            check_if_limits_reached()

        def reached_max_consecutive_pages_retrieved():
            max_consecutive_pages_retrieved = hashtag.max_consecutive_pages_retrieved or \
                                                  settings.MAX_CONSECUTIVE_PAGES_RETRIEVED_PER_HASHTAG_EXTRACTION
            if num_pages_retrieved == max_consecutive_pages_retrieved:
                settings.LOGGER.info('%sExtractor %s reached max consecutive pages retrieved for hashtag (%i)' %
                                      (pre_msg, self.twitter_bot.username, hashtag.max_consecutive_pages_retrieved))
                return True

        try:
            self.connect_twitter_api()
            self.log_being_used()
            pre_msg = hashtag.pre_msg_for_logs()

            settings.LOGGER.info('%sExtraction started' % pre_msg)

            num_pages_retrieved = 0

            while True:
                process_page()
                num_pages_retrieved += 1
                if reached_max_consecutive_pages_retrieved():
                    break
        except tweepy.error.TweepError as e:
            self.handle_tweeperror(e, hashtag=hashtag)

    def handle_tweeperror(self, tweeperr, targetuser=None, hashtag=None):
        if not tweeperr.response and 'Cannot connect to proxy' in tweeperr.reason:
            check_internet_connection_works()
        elif hasattr(tweeperr.response, 'status_code'):

            # rate limited
            if tweeperr.response.status_code == 429:
                raise RateLimitedException(self)

            # targetuser suspended
            elif tweeperr.response.status_code == 403 and targetuser:
                r = simplejson.loads(tweeperr.response.text)
                targ_user_suspended = 'errors' in r and 'code' in r['errors'][0] and r['errors'][0]['code'] == 63
                if targ_user_suspended:
                    raise TargetUserWasSuspended(targetuser)

            # over capacity
            elif tweeperr.response.status_code == 503:
                pass
        else:
            settings.LOGGER.exception('tweepy error')
            time.sleep(7)
            raise tweeperr

class Hashtag(models.Model):
    q = models.CharField(max_length=140, null=False)
    geocode = models.CharField(max_length=50, null=True, blank=True)
    lang = models.CharField(max_length=2, null=True, blank=True)
    
    # todo: de momento sólo es válido el modo recent
    MIXED = 1
    RECENT = 2
    POPULAR = 3
    RESULT_TYPES = (
        (MIXED, 'mixed'),
        (RECENT, 'recent'),
        (POPULAR, 'popular'),
    )
    result_type = models.PositiveIntegerField(null=False, choices=RESULT_TYPES, default=2)

    # sirve para indicar por qué id de tweet íbamos para poder extraer siguiente página de tweets
    max_id = models.BigIntegerField(null=True, blank=True)

    # cuenta de nuevos twitterusers obtenidos durante la ronda actual
    current_round_user_count = models.IntegerField(null=True, blank=True)
    # límite de tweet más antiguo para la ronda actual y siguiente
    current_round_oldest_tweet_limit = models.DateTimeField(null=True, blank=True)
    next_round_oldest_tweet_limit = models.DateTimeField(null=True, blank=True)

    # fecha en la que se terminó de extraer la última ronda
    last_round_end_date = models.DateTimeField(null=True, blank=True)

    # aquí marcamos manualmente si lo usamos o no
    is_active = models.BooleanField(default=True)

    # aquí se marca si tiene que esperar periodo ventana desde última extracción que lanzaba la excepción
    # anunciando que no se obtenían suficientes usuarios
    has_to_wait_timewindow_because_of_not_enough_new_twitterusers = models.BooleanField(default=False)

    # fecha en la que se extrajo una página por última vez
    date_last_extraction = models.DateTimeField(null=True, blank=True)

    # máximo de páginas consecutivas que el extractor toma para este hashtag
    # podemos cambiar este valor para dar más prioridad a un hashtag u otro
    max_consecutive_pages_retrieved = models.PositiveIntegerField(null=False, blank=False, default=10)

    num_consecutive_pages_without_enough_new_twitterusers = models.PositiveIntegerField(null=True, default=0)


    twitter_users = models.ManyToManyField('TwitterUser', through='TwitterUserHasHashtag',
                                           related_name='hashtags', blank=True)

    objects = HashtagManager()

    def __unicode__(self):
        return self.q

    def extract_twitterusers(self):
        """Extrae twitterusers que tuitearon con el hashtag"""

        available_extractors = Extractor.objects.available(Extractor.HASHTAG_MODE)
        if available_extractors.exists():
            for extractor in available_extractors:
                try:
                    extractor.extract_twitterusers_from_hashtag(self)
                except TweepError as e:
                    if 'Cannot connect to proxy' in e.reason:
                        settings.LOGGER.exception('Extractor %s can\'t connect to proxy %s' %
                                                      (extractor.twitter_bot.username,
                                                       extractor.twitter_bot.proxy_for_usage.__unicode__()))
                        # si no podemos conectar al proxy del extractor vamos al siguiente
                        continue
                    else:
                        raise e
                except RateLimitedException:
                    # si el extractor superó el ratio de peticiones pasamos al siguiente
                    continue
                except (HashtagOlderTweetDateLimitReached,
                        HashtagMaxUsersCountReached,
                        HashtagReachedConsecutivePagesWithoutEnoughNewTwitterusers,
                        HashtagExtractionWithoutResults,
                        InternetConnectionError):
                    break

            time.sleep(random.randint(1, 5))
        else:
            raise NoAvaiableExtractors(Extractor.HASHTAG_MODE)

    def go_to_next_round(self):
        """Esto se hace para que se vuelva a extraer empezando por los tweets más recientes, hasta que se llegue
        a la fecha del tweet más reciente de la ronda anterior"""
        self.max_id = None
        self.current_round_oldest_tweet_limit = self.next_round_oldest_tweet_limit
        self.next_round_oldest_tweet_limit = None
        self.current_round_user_count = 0
        self.last_round_end_date = utc_now()
        self.save()

    def round_just_begun(self):
        """Nos dice si acaba de comenzar la ronda para la extracción actual, bien por comenzar por primera vez o porque
        el hashtag pasara de ronda para volver tomar tweets más recientes"""
        return not self.max_id

    def is_in_first_round(self):
        return not self.last_round_end_date

    def has_too_many_pages_without_enough_new_twitterusers(self):
        return self.num_consecutive_pages_without_enough_new_twitterusers >= \
               settings.HASHTAG_EXTRACTION_MAX_CONSECUTIVE_PAGES_RETRIEVED_WITHOUT_ENOUGH_NEW_TWITTERUSERS

    def check_if_enough_new_twitterusers(self, new_twitterusers):
        """Mira si el número de followers tomados desde la página extraída es menor
        que el umbral establecido

        :param new_twitterusers - nuevos twitterusers sacados de la página tomada por el extractor
        """
        min_expected = settings.HASHTAG_EXTRACTION_MIN_NEW_TWITTERUSERS_PER_PAGE_EXPECTED
        if len(new_twitterusers) < min_expected:
            self.num_consecutive_pages_without_enough_new_twitterusers += 1
            settings.LOGGER.warning('%sNot enough new twitterusers retrieved from page (%d, min expected: %d). '
                                    '%i consecutive pages without enough new twitterusers' %
                                    (self.pre_msg_for_logs(), len(new_twitterusers), min_expected,
                                     self.num_consecutive_pages_without_enough_new_twitterusers))
        else:
            self.num_consecutive_pages_without_enough_new_twitterusers = 0
        self.save()

        if self.has_too_many_pages_without_enough_new_twitterusers():
            raise HashtagReachedConsecutivePagesWithoutEnoughNewTwitterusers(self)
        elif self.has_to_wait_timewindow_because_of_not_enough_new_twitterusers:
            self.has_to_wait_timewindow_because_of_not_enough_new_twitterusers = False
            self.save()

    def mark_as_inactive(self):
        self.is_active = False
        self.save()

    def pre_msg_for_logs(self):
        return '[#: %s] >> ' % self.__unicode__()

    def timewindow_waiting_for_next_round_passed(self):
        return self.last_round_end_date and self.last_round_end_date <= \
                                            (utc_now() - datetime.timedelta(seconds=settings.NEW_ROUND_TIMEWINDOW))
    timewindow_waiting_for_next_round_passed.boolean = True

    def timewindow_waiting_since_not_enough_twitterusers_passed(self):
        return not self.has_to_wait_timewindow_because_of_not_enough_new_twitterusers \
               or \
               self.date_last_extraction <= \
               utc_now() - datetime.timedelta(seconds=settings.HASHTAG_TIMEWINDOW_TO_WAIT_WHEN_NOT_ENOUGH_TWITTERUSERS)
    timewindow_waiting_since_not_enough_twitterusers_passed.boolean = True

    def is_available_to_extract(self):
        return self.timewindow_waiting_for_next_round_passed() and \
               self.timewindow_waiting_since_not_enough_twitterusers_passed()
    is_available_to_extract.boolean = True

    def get_max_consecutive_pages_retrieved_per_extraction(self):
        return self.max_consecutive_pages_retrieved or \
               settings.MAX_CONSECUTIVE_PAGES_RETRIEVED_PER_HASHTAG_EXTRACTION

class TUGroup(models.Model):
    name = models.CharField(max_length=140, null=False, blank=False)
    target_users = models.ManyToManyField(TargetUser, related_name='tu_groups', null=False, blank=False)
    projects = models.ManyToManyField(Project, related_name='tu_groups', null=False, blank=False)

    def __unicode__(self):
        return self.name
        # tu_group_string = ' -'
        # for tu in self.target_users.all():
        #     tu_group_string += ' @' + tu.username
        # return self.name + tu_group_string


class HashtagGroup(models.Model):
    name = models.CharField(max_length=140, null=False, blank=False)
    hashtags = models.ManyToManyField(Hashtag, related_name='hashtag_groups', null=False, blank=False)
    projects = models.ManyToManyField(Project, related_name='hashtag_groups', null=False, blank=False)

    def __unicode__(self):
        hashtag_group_string = ' -'
        for ht in self.hashtags.all():
            hashtag_group_string += ' ' + ht.q
        return self.name + hashtag_group_string

# class TargetUser_TUGroup:
#     target_user = models.ForeignKey(TargetUser, null=False, blank=False, related_name='target_user')
#     tu_group = models.ForeignKey(TUGroup, null=False, blank=False, related_name='tu_group')
#
#     def __unicode__(self):
#         return '%s %s' % (self.target_user.username, self.tu_group.name)

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
        return '#' + self.name


class PageLink(models.Model):
    page_title = models.CharField(max_length=150, null=True, blank=True)
    page_link = models.URLField(null=False, blank=False)
    project = models.ForeignKey(Project, related_name='pagelinks', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    hashtags = models.ManyToManyField(PageLinkHashtag, null=True, blank=True, related_name="page_links")
    image = models.ForeignKey(TweetImg, null=True, blank=True, related_name="page_img")
    language = models.CharField(max_length=2, null=True, blank=True)

    def __unicode__(self):
        return self.compose()

    def compose(self, with_link=True):
        elements = []
        if self.page_title:
            elements.append(self.page_title)
        if with_link and self.page_link:
            elements.append(self.page_link)
        if self.hashtags.exists():
            elements.extend([hashtag.__unicode__() for hashtag in self.hashtags.all()])

        return ' '.join(elements)

    def length(self, p=None):
        page_link_length = settings.TWEET_LINK_LENGTH
        if self.page_title:
            page_link_length += 1 + len(self.page_title)
        try:
            if p.cleaned_data:
                if p.cleaned_data['hashtags']:
                    for hastag in p.cleaned_data['hashtags']:
                        page_link_length += 1 + len(hastag.name)
        except:
            pass
        if self.image:
            page_link_length += settings.TWEET_IMG_LENGTH
        return page_link_length


class ProxiesGroup(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False)

    avatar_required_to_send_tweets = models.BooleanField(default=False)
    bio_required_to_send_tweets = models.BooleanField(default=False)

    # bot registration behaviour
    is_bot_creation_enabled = models.BooleanField(default=False)
    max_tw_bots_per_proxy_for_registration = models.PositiveIntegerField(null=False, blank=False, default=6)
    min_days_between_registrations_per_proxy = models.PositiveIntegerField(null=False, blank=False, default=5)
    min_days_between_registrations_per_proxy_under_same_subnet = models.PositiveIntegerField(null=False, blank=False, default=2)

    # si queremos usar proxies limpitos para meterle bots que hayan sido suspendidos
    reuse_proxies_with_suspended_bots = models.BooleanField(default=False)

    # bot usage behaviour
    is_bot_usage_enabled = models.BooleanField(default=False)
    max_tw_bots_per_proxy_for_usage = models.PositiveIntegerField(null=False, blank=False, default=12)

    # tweet behaviour
    time_between_tweets = models.CharField(max_length=10, null=False, blank=False, default='2-7')  # '2-5' -> entre 2 y 5 minutos
    # tweets_per_burst = models.CharField(max_length=10, null=False, blank=False, default='15-20')
    has_tweet_msg = models.BooleanField(default=False)
    has_link = models.BooleanField(default=False)
    has_tweet_img = models.BooleanField(default=False)
    has_page_announced = models.BooleanField(default=False)
    has_mentions = models.BooleanField(default=False)
    max_num_mentions_per_tweet = models.PositiveIntegerField(null=False, blank=False, default=1)
    feedtweets_per_twitteruser_mention = models.CharField(max_length=10, null=False, blank=False, default='0-3')

    #
    # mentioning check behaviour
    #
    #  cada x menciones consecutivas se manda un tweet a otro bot de su mismo grupo para ver si sigue funcionando
    num_consecutive_mentions_for_check_mentioning_works = models.PositiveIntegerField(null=False, blank=False, default=20)
    # time window para no volver a mencionar con el mismo robot después de que la comprobación haya ido mal
    mention_fail_time_window = models.CharField(max_length=10, null=False, blank=False, default='10-40')
    # time window desde que se envía el mc_tweet hasta que el bot destino lo verifica en su panel de notificaciones
    destination_bot_checking_time_window = models.CharField(max_length=10, null=False, blank=False, default='4-6')
    # tiempo mínimo que ha de pasar para que un bot pueda mandar mctweet otra vez a un mismo bot
    mctweet_to_same_bot_time_window = models.CharField(max_length=10, null=False, blank=False, default='60-120')

    #
    # following behaviour
    #
    # si se pone a seguir o no a gente
    has_following_activated = models.BooleanField(default=False)
    # máximo de following en relación a seguidores
    following_ratio = models.CharField(max_length=10, null=False, blank=False, default='0.5-3')
    # periodo ventana (en horas) para comprobar ratio y seguir a gente si es bajo
    time_window_to_follow = models.CharField(max_length=10, null=False, blank=False, default='12-48')
    # máximo de usuarios que sigue de una tacada
    max_num_users_to_follow_at_once = models.CharField(max_length=10, null=False, blank=False, default='1-8')

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

    def is_full_of_bots_using(self):
        """Nos dice si en el grupo todos sus proxies están completos de robots en uso"""
        working_proxies = self.proxies.connection_ok()
        max_bots_num = working_proxies.count() * self.max_tw_bots_per_proxy_for_usage
        return self.get_bots_using().count() >= max_bots_num

    def get_bots_using(self):
        """Saca bots que hay usándose bajo el grupo de proxies"""
        from core.models import TwitterBot
        return TwitterBot.objects.filter(proxy_for_usage__proxies_group=self)


    def get_num_bots_left_for_reg_usage(self):
        """Saca el número de bots que quedan para que se completen todos los proxies del grupo"""
        ok_proxies = self.proxies.connection_ok()
        reg_sum = 0
        usage_sum = 0
        for proxy in ok_proxies:
            reg_sum += proxy.twitter_bots_registered.count()
            usage_sum += proxy.twitter_bots_using.count()

        ok_proxies_count = ok_proxies.count()
        num_bots_for_reg_left = (self.max_tw_bots_per_proxy_for_registration * ok_proxies_count) - reg_sum
        num_bots_for_usage_left = (self.max_tw_bots_per_proxy_for_usage * ok_proxies_count) - usage_sum

        return num_bots_for_reg_left, num_bots_for_usage_left



class Feed(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False, default='_unnamed')
    url = models.URLField(null=False, blank=False, unique=True)

    def __unicode__(self):
        return self.name

    def get_new_item(self):
        """Saca un item del feed que todavía no esté guardado en tabla FeedItem de nuestra BD"""
        feed = feedparser.parse(self.url)
        for entry in feed['entries']:
            entry_text = entry['title']
            entry_link = entry['feedburner_origlink'] if 'feedburner_origlink' in entry else entry['link']

            text_is_short_enough = len(entry_text) <= 101
            text_is_new = not FeedItem.objects.filter(text__icontains=entry_text).exists()

            if text_is_short_enough and text_is_new:
                return FeedItem(feed=self, text=entry_text, link=entry_link)

        return None


class FeedItem(models.Model):
    feed = models.ForeignKey(Feed, null=False, blank=False)
    text = models.CharField(max_length=101, null=False, blank=False)
    link = models.URLField(null=True, blank=True)
    date_saved = models.DateTimeField(auto_now_add=True)

    objects = FeedItemManager()

    def __unicode__(self):
        return '%s %s' % (self.text, self.link)


class FeedsGroup(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False)
    feeds = models.ManyToManyField(Feed, related_name='feeds_groups', null=True, blank=True)
    proxies_groups = models.ManyToManyField(ProxiesGroup, related_name='feeds_groups', null=True, blank=True)

    def __unicode__(self):
        return self.name


class TweetFromFeed(models.Model):
    tweet = models.OneToOneField('Tweet', related_name='tweet_from_feed', null=False, blank=False)
    tu_mention = models.ForeignKey('Tweet', related_name='tweets_from_feed')


class FTweetsNumPerTuMention(models.Model):
    number = models.PositiveIntegerField(null=False, blank=False, default=0)
    tu_mention = models.OneToOneField('Tweet', related_name='ftweets_num')


class TwitterBotFollowing(models.Model):
    # si el bot le dió o no a seguir
    performed_follow = models.BooleanField(default=False)

    # si se produjo el seguimiento correctamente
    followed_ok = models.BooleanField(default=False)

    date_followed = models.DateTimeField(null=True, blank=True)

    bot = models.ForeignKey('core.TwitterBot', related_name='tb_followings')
    twitteruser = models.ForeignKey('TwitterUser', related_name='tb_followings')

    def __unicode__(self):
        return self.bot.username + ' -> ' + self.twitteruser.username