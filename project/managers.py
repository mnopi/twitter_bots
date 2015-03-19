# -*- coding: utf-8 -*-

import time
import random
from django.db.models import Q, Count
from django.db.models.query import QuerySet
from tweepy import TweepError
from core.decorators import mlocked
from core.managers import MyManager
from core.scrapper.exceptions import TwitterAccountSuspended, ProxyConnectionError, \
    TargetUserWasSuspended, InternetConnectionError
from core.scrapper.utils import has_elapsed_secs_since_time_ago
from core.scrapper.utils import generate_random_secs_from_minute_interval
from project.exceptions import *
from project.querysets import ProjectQuerySet, TwitterUserQuerySet, TweetQuerySet, ExtractorQuerySet, TargetUserQuerySet, \
    FeedItemQuerySet, HashtagQuerySet
from twitter_bots import settings
from django.db import models


class TargetUserManager(models.Manager):
    def create(self, **kwargs):
        target_user_created = super(TargetUserManager, self).create(**kwargs)
        target_user_created.complete_creation()

    # QUERYSETS

    def get_queryset(self):
        return TargetUserQuerySet(self.model, using=self._db)

    def available_to_extract(self):
        return self.get_queryset().available_to_extract()

    def for_project(self, project):
        return self.get_queryset().for_project(project)


class HashtagManager(models.Manager):

    # QUERYSETS

    def get_queryset(self):
        return HashtagQuerySet(self.model, using=self._db)

    def for_project(self, project):
        return self.get_queryset().for_project(project)

    def available_to_extract(self):
        return self.get_queryset().available_to_extract()


class TweetManager(MyManager):
    def all_sent_ok(self):
        "Devuelve si en BD todos los tweets están marcados como enviados"
        return self.get_sent_ok().count() == self.all().count()

    def clean_not_sent_ok(self, bot_used=None):
        f = {
            'sent_ok': False
        }
        if bot_used:
            f.update(bot_used=bot_used)

        tweets_to_delete = self.filter(**f)
        if tweets_to_delete.exists():
            tweets_to_delete_count = tweets_to_delete.count()
            tweets_to_delete.delete()
            settings.LOGGER.info('Deleted tweets pending to send%s from queue (%d)' %
                                 (' for bot %s' % bot_used if bot_used else '', tweets_to_delete_count))

    def put_sending_to_not_sending(self):
        if self.exists():
            self.filter(sending=True).update(sending=False)
            settings.LOGGER.info('All previous sending tweets (mutweets, mctweets or ftweets) were set to not sending')

    def create_mentions_to_send(self):
        """Crea los tweets a encolar para cada bot disponible"""

        from project.models import Project, TwitterUser, Tweet
        from core.models import TwitterBot

        def create_mentions_for_project(project):

            def get_bots_to_send_mentions():
                # tomamos los bots como resultado de aplicar los filtros en el siguiente orden:
                #   - que pertenezcan al proyecto actual
                #   - que su proxy funcione ok
                #   - que no tenga llena su cola de menciones pendientes por enviar
                bots_to_send_mentions = None

                bots_for_project = TwitterBot.objects.usable_regardless_of_proxy()\
                    .using_in_project(project)
                if bots_for_project.exists():
                    # antes de filtrar por proxies ok comprobamos en cada uno si sus proxy sigue funcionando
                    TwitterBot.objects.check_proxies(bots_for_project)
                    bots_working_ok = bots_for_project.with_proxy_connecting_ok()
                    if bots_working_ok.exists():
                        bots_with_free_queue = bots_for_project.without_tweet_to_send_queue_full()
                        if bots_with_free_queue.exists():
                            bots_to_send_mentions = bots_with_free_queue
                        else:
                            settings.LOGGER.info('Project %s has queue full of twitteruser mentions at this moment'
                                                 % project.name)
                    else:
                        settings.LOGGER.error('Project %s has %i usable bots, but none has working proxy ok.'
                                              % (project.name, bots_for_project.count()))
                else:
                    settings.LOGGER.error('Project %s has no bots assigned and will be stopped' % project.name)
                    project.is_running = False
                    project.save()

                if not bots_to_send_mentions:
                    raise ProjectWithoutBotsToSendMentions
                else:
                    return bots_to_send_mentions

            def fetch_unmentioned_twitterusers_if_not(lang):
                if lang not in unmentioned_twitterusers and lang not in discarded_langs:
                    unmentioned_twitterusers[lang] = list(TwitterUser.objects.get_unmentioned_on_project(
                        project,
                        limit=max_unmentioned_fetched_per_lang,
                        language=None if lang_used == 'all' else lang_used
                    ))

                    if not unmentioned_twitterusers[lang]:
                        settings.LOGGER.error('Project %s has no unmentioned twitterusers with lang: %s' % (project.name, lang))
                        discarded_langs.append(lang)

            # obtenemos los usuarios a mencionar para cada lenguaje de los usados en el proyecto
            unmentioned_twitterusers = {}

            # metemos aquí los idiomas que queramos descartar por no encontrarse unmentioned con ese idioma
            discarded_langs = []

            bots = get_bots_to_send_mentions()
            max_unmentioned_fetched_per_lang = bots.count()
            for bot in bots:

                lang_used = None
                pagelink = None
                tweet_msg = None

                project_pagelinks = project.pagelinks.filter(is_active=True)
                if project_pagelinks.exists():
                    pagelink = project_pagelinks.order_by('?').first()
                    lang_used = pagelink.language
                else:
                    project_msgs = project.tweet_msgs
                    if project_msgs.exists():
                        tweet_msg = project_msgs.order_by('?').first()
                        lang_used = tweet_msg.language

                # si el idioma del texto del tweet es en inglés se escoge cualquier twitteruser
                lang_used = 'all' if not lang_used else lang_used

                fetch_unmentioned_twitterusers_if_not(lang_used)

                if lang_used not in discarded_langs:
                    tweet_to_send = Tweet(
                        project=project,
                        bot_used=bot
                    )
                    if pagelink:
                        tweet_to_send.page_announced = pagelink
                    elif tweet_msg:
                        tweet_to_send.tweet_msg = tweet_msg
                    else:
                        raise ProjectHasNoMsgLinkOrPagelink(project)

                    project_links = project.links.filter(is_active=True)
                    if project_links.exists():
                        tweet_to_send.link = project_links.order_by('?').first()

                    project_imgs = project.tweet_imgs.filter(is_using=True)
                    if project_imgs.exists():
                        tweet_to_send.tweet_img = project_imgs.order_by('?').first()

                    try:
                        twitteruser_to_mention = unmentioned_twitterusers[lang_used][0]
                    except IndexError:
                        settings.LOGGER.error('Project %s has no more unmentioned twitterusers with lang: %s' % (project.name, lang_used))
                        discarded_langs.append(lang_used)
                    else:
                        tweet_to_send.save()
                        tweet_to_send.mentioned_users.add(twitteruser_to_mention)
                        unmentioned_twitterusers[lang_used].remove(twitteruser_to_mention)

                        settings.LOGGER.info('Queued [proj: %s | bot: %s] >> %s' %
                                     (project.__unicode__(), tweet_to_send.bot_used.__unicode__(), tweet_to_send.compose()))

        running_projects = Project.objects.running().order_by__queued_tweets()
        if running_projects.exists():
            settings.LOGGER.info('Creating mentions for running project(s): %s' %
                                 Project.objects.get_names_list(running_projects))
            for project in running_projects:
                try:
                    create_mentions_for_project(project)
                except (ProjectWithoutBotsToSendMentions,
                        ProjectHasNoMsgLinkOrPagelink):
                    continue
        else:
            settings.LOGGER.warning('No projects running at this moment')

    def get_queued_twitteruser_mentions_to_send(self, by_bot=None):
        """De entre los tweets encolados devuelve 1 por bot que pueda enviar"""

        queue = self.raw_as_qs("""
            select
                project_tweet.id,
                core_twitterbot.id,

                #
                # sender sending
                #
                # (select count(project_tweet.id) > 0 AS sender_already_sending
                #     from project_tweet where project_tweet.sending=True and project_tweet.bot_used_id = core_twitterbot.id
                # ) as sender_already_sending,

                #
                # sender verifying
                #
                # (select count(project_tweetcheckingmention.id) > 0 AS sender_verifying
                #     from project_tweet
                #     left outer join project_tweet_mentioned_bots on project_tweet.id = project_tweet_mentioned_bots.tweet_id
                #     left outer join project_tweetcheckingmention ON project_tweet.id = project_tweetcheckingmention.tweet_id
                #     where
                #     project_tweet_mentioned_bots.twitterbot_id = core_twitterbot.id
                #     and project_tweetcheckingmention.destination_bot_is_checking_mention = True
                # ) as sender_verifying,

                #
                # tweeting time window passed
                #
                (SELECT max(project_tweet.date_sent) as max
                    FROM project_tweet
                    WHERE
                    project_tweet.sent_ok = True
                    and project_tweet.bot_used_id = core_twitterbot.id
                ) as last_tweet_date,
                (select project_proxiesgroup.time_between_tweets
                    from project_proxiesgroup
                    inner join core_proxy on project_proxiesgroup.id = core_proxy.proxies_group_id
                    where core_twitterbot.proxy_for_usage_id = core_proxy.id
                ) as time_between_tweets,
                (SELECT SUBSTRING_INDEX(time_between_tweets, '-', 1)) as min_time,
                (SELECT SUBSTRING_INDEX(time_between_tweets, '-', -1)) as max_time,
                (select ROUND(RAND() * (max_time*60 - min_time*60)) + min_time*60) as random_secs,
                (select DATE_SUB(UTC_TIMESTAMP(), INTERVAL random_secs SECOND)) as last_tweet_min_date,
                (select last_tweet_min_date >= last_tweet_date or last_tweet_date is null) as timewindow_passed

            from project_tweet

            left outer join core_twitterbot on project_tweet.bot_used_id=core_twitterbot.id
            left outer JOIN project_tweet_mentioned_users ON (project_tweet.id = project_tweet_mentioned_users.tweet_id)

            where
                project_tweet.sending=False
                and project_tweet.sent_ok=False
                and project_tweet_mentioned_users.twitteruser_id is not null
                and core_twitterbot.is_being_used=False

            group by core_twitterbot.id

            having timewindow_passed = True
            #     sender_already_sending = False
            #     and sender_verifying = False
        """
        )

        if by_bot:
            queue = queue.by_bot(by_bot)

        return queue

    def clean_not_ok(self):
        from project.models import TweetCheckingMention, Project

        # eliminamos los tweets de los proyectos que no estén corriendo actualmente y que no se hayan enviado,
        # juntos a los ftweets y mctweets que también quedaran sin enviar
        self.filter(
            (
                Q(project__in=Project.objects.filter(is_running=False)) |
                Q(project__isnull=True)
            ),
            sent_ok=False
        ).delete()

        self.pending_to_send().with_not_ok_bots().delete()
        self.put_sending_to_not_sending()
        TweetCheckingMention.objects.put_checking_to_not_checking()

    def clear_queue_to_send(self):
        not_sent_ok = self.filter(sent_ok=False)
        count = not_sent_ok.count()
        if count > 0:
            not_sent_ok.delete()
            settings.LOGGER.info('Tweet queue cleared (%d tweets not sent removed)' % count)
        else:
            settings.LOGGER.info('Tweet queue was empty before doing this')

    def clear_mctweets_not_verified(self):
        """Elimina aquellos mctweets pendientes de verificar. Esto es útil cuando cambiamos el mensaje
        de un tweet, de manera que se vuelva a enviar mctweet y no compararlo en el bot receptor con el
        mensaje antiguo"""
        mctweets_not_verified = self.mctweets_not_verified()
        count = mctweets_not_verified.count()
        if count > 0:
            mctweets_not_verified.delete()
            settings.LOGGER.info('Deleted %d mctweets not verified' % count)
        else:
            settings.LOGGER.info('There are no mctweets not verified to delete')

    def process_mention(self, mention_pk, burst_size=None):
        mention = self.get(pk=mention_pk)
        return mention.process_sending(burst_size=burst_size)


    #
    # proxy queryset methods
    #

    def get_queryset(self):
        return TweetQuerySet(self.model, using=self._db)

    def sent_ok(self):
        return self.get_queryset().sent_ok()

    def by_bot(self, bot):
        return self.get_queryset().by_bot(bot)

    def mentioning_bots(self):
        return self.get_queryset().mentioning_bots()

    def not_checked_if_mention_arrives_ok(self):
        return self.get_queryset().not_checked_if_mention_arrives_ok()

    def pending_to_send(self):
        return self.get_queryset().pending_to_send()

    def with_not_ok_bots(self):
        return self.get_queryset().with_not_ok_bots()

    def mctweets(self):
        return self.get_queryset().mctweets()

    def mctweets_not_verified(self):
        return self.get_queryset().mctweets_not_verified()


class ProjectManager(models.Manager):

    def check_bots_on_all_running(self):
        """Comprueba que haya bots en todos los proyectos que estén marcados en ejecución"""
        running_projects = self.running()
        for project in running_projects:
            project_bots = project.get_twitteable_bots()
            if project_bots.exists():
                settings.LOGGER.info('Running project "%s" with %d bots..' %
                                     (project.name, project_bots.count()))
            else:
                raise ProjectRunningWithoutBots(project)

    def get_names_list(self, projects):
        """Imprime los nombres de los proyectos dados separando por ,"""
        try:
            list = [project.name for project in projects]
        except TypeError:
            list =  projects.values_list('name', flat=True)

        return ', '.join(list)

    # QUERYSET

    def get_queryset(self):
        return ProjectQuerySet(self.model, using=self._db)

    def running(self):
        return self.get_query_set().running()

    def with_bot(self, bot):
        return self.get_queryset().with_bot(bot)

    def with_unmentioned_users(self):
        return self.get_query_set().with_unmentioned_users()

    def order_by__queued_tweets(self, direction=''):
        return self.get_query_set().order_by__queued_tweets(direction)


class ExtractorManager(MyManager):
    def extract_twitterusers_for_running_projects(self):
        from project.models import Project, TwitterUser

        # limpiamos los antiguos todavía sin mencionar
        TwitterUser.objects.clear_old_unmentioned()

        # vamos iterando por cada uno de los proyectos en ejecución
        running_projects = Project.objects.filter(is_running=True)
        if running_projects.exists():
            for project in running_projects:
                try:
                    project.check_if_full_of_unmentioned_twitterusers()
                    project.extract_twitterusers()
                except (ProjectFullOfUnmentionedTwitterusers,
                        ProjectHasNoTwitterusersToExtract):
                    # si el proyecto está repleto de usuarios sin mencionar se pasa al siguiente que haya en ejecución
                    continue
        else:
            raise NoRunningProjects

    def get_one_available_extractor(self, mode):
        """Saca un extractor que haya disponible, previamente conectado a la API de twitter"""

        available_extractors = self.available(mode=mode)
        if available_extractors.exists():
            extractor = available_extractors.first()
            extractor.connect_twitter_api()
            extractor.log_being_used()
        else:
            raise NoAvaiableExtractors

    # QUERYSETS

    def get_queryset(self):
        return ExtractorQuerySet(self.model, using=self._db)

    def available(self, mode):
        return self.get_queryset().available(mode)


class ProxiesGroupManager(MyManager):
    def log_groups(self, groups, with_field):
        if groups.exists():
            groups_str = ', '.join([group.name for group in groups])
            settings.LOGGER.info('%d groups with %s: %s' %
                                    (groups.count(), with_field, groups_str))
        else:
            settings.LOGGER.info('No groups with %s' % with_field)

    def log_groups_with_creation_enabled_disabled(self):
        groups_with_creation_enabled = self.filter(is_bot_creation_enabled=True)
        self.log_groups(groups_with_creation_enabled, 'bot creation enabled')

        groups_with_creation_disabled = self.filter(is_bot_creation_enabled=False)
        self.log_groups(groups_with_creation_disabled, 'bot creation disabled')

    def log_groups_with_usage_disabled(self):
        groups_with_usage_disabled = self.filter(is_bot_usage_enabled=False)
        if groups_with_usage_disabled.exists():
            groups_str = ', '.join([group.name for group in groups_with_usage_disabled])
            settings.LOGGER.warning('There are %d groups that have bot usage disabled: %s' %
                                    (groups_with_usage_disabled.count(), groups_str))


class TwitterUserManager(MyManager):
    def get_unmentioned_on_project(self, project, limit=None, language=None):
        """
            Saca usuarios no mencionados que pertenezcan a ese proyecto. Tampoco saca los mencionados
            por otro proyecto, es decir que nunca los mencionó ningún bot.

            Los saca ordenados por el último tweet que hicieron, de más recientes a más antiguos.

        :param project: proyecto sobre el que están guardados a través de target_users y hashtags
        :param limit: máximo de usuarios que queremos sacar en la consulta
        :return: queryset con los objetos twitteruser
        """

        return self.raw_as_qs("""
            SELECT project_users.id
            FROM
                (
                    (
                        select twitteruser.id, twitteruser.last_tweet_date
                        %(language_field)s
                        from project_twitteruser as twitteruser
                        LEFT OUTER JOIN project_follower as follower ON (twitteruser.id = follower.twitter_user_id)
                        LEFT OUTER JOIN project_targetuser as targetuser ON (follower.target_user_id = targetuser.id)
                        LEFT OUTER JOIN project_project_target_users as proj_targetusers ON (targetuser.id = proj_targetusers.targetuser_id)
                        WHERE proj_targetusers.project_id = %(project_pk)d
                    )
                    union
                    (
                        select twitteruser.id, twitteruser.last_tweet_date
                        %(language_field)s
                        from project_twitteruser as twitteruser
                        LEFT OUTER JOIN project_twitteruserhashashtag as twitteruser_hashtag ON (twitteruser.id = twitteruser_hashtag.twitter_user_id)
                        LEFT OUTER JOIN project_hashtag as hashtag ON (twitteruser_hashtag.hashtag_id = hashtag.id)
                        LEFT OUTER JOIN project_project_hashtags as project_hashtags ON (hashtag.id = project_hashtags.hashtag_id)
                        WHERE project_hashtags.project_id = %(project_pk)d
                    )
                    union
                    (
						select twitteruser.id, twitteruser.last_tweet_date
						%(language_field)s
						from project_twitteruser as twitteruser
						LEFT OUTER JOIN project_follower as follower ON (twitteruser.id = follower.twitter_user_id)
						LEFT OUTER JOIN project_targetuser as targetuser ON (follower.target_user_id = targetuser.id)
						LEFT OUTER JOIN project_tugroup_target_users as tugroup_targetusers ON (targetuser.id = tugroup_targetusers.targetuser_id)
						LEFT OUTER JOIN project_tugroup as tugroup ON (tugroup_targetusers.tugroup_id = tugroup.id)
						LEFT OUTER JOIN project_tugroup_projects as tugroup_projects ON (tugroup.id = tugroup_projects.tugroup_id)
						WHERE tugroup_projects.project_id = %(project_pk)d
                    )
                    union
                    (
						select twitteruser.id, twitteruser.last_tweet_date
						%(language_field)s
						from project_twitteruser as twitteruser
						LEFT OUTER JOIN project_twitteruserhashashtag as twitteruser_hashtag ON (twitteruser.id = twitteruser_hashtag.twitter_user_id)
						LEFT OUTER JOIN project_hashtag as hashtag ON (twitteruser_hashtag.hashtag_id = hashtag.id)
						LEFT OUTER JOIN project_hashtaggroup_hashtags as hgroup_hashtags ON (hashtag.id = hgroup_hashtags.hashtag_id)
						LEFT OUTER JOIN project_hashtaggroup as hgroup ON (hgroup_hashtags.hashtaggroup_id = hgroup.id)
						LEFT OUTER JOIN project_hashtaggroup_projects as hgroup_projects ON (hgroup.id = hgroup_projects.hashtaggroup_id)
						WHERE hgroup_projects.project_id = %(project_pk)d
                    )
                ) project_users
            LEFT OUTER JOIN project_tweet_mentioned_users as tweet_mentionedusers ON (project_users.id = tweet_mentionedusers.twitteruser_id)
            WHERE tweet_mentionedusers.tweet_id IS NULL
            %(language)s
            ORDER BY project_users.last_tweet_date DESC
            %(limit)s
            """ %
            {
                'project_pk': project.pk,
                'limit': 'LIMIT %d' % limit if limit else '',
                'language': 'and project_users.language="%s"' % language if language and language != 'en' else '',
                'language_field': ', twitteruser.language' if language else ''
            }
        )

    def clear_old_unmentioned(self):
        """Elimina los followers extraídos hace más de x días y que aún no fueron mencionados"""
        old_unmentioned = self.unmentioned().saved_lte_days(settings.MAX_DAYS_TO_STAY_UNMENTIONED)
        count = old_unmentioned.count()
        if count > 0:
            old_unmentioned.delete()
            settings.LOGGER.info('Deleted %i old unmentioned twitterusers' % count)

    def clear_all_unmentioned(self):
        """Elimina todos los twitterusers extraídos y que no fueron aún mencionados"""
        unmentioned = self.unmentioned()
        if unmentioned.exists():
            count = unmentioned.count()
            unmentioned.delete()
            settings.LOGGER.info('All unmentioned twitterusers were deleted (%i)' % count)
        else:
            settings.LOGGER.info('There are no unmentioned twitterusers, so nothing could be deleted.')

    # PROXY QUERYSET
    def get_queryset(self):
        return TwitterUserQuerySet(self.model, using=self._db)

    def for_project(self, project):
        return self.get_queryset().for_project(project)

    def mentioned(self):
        return self.get_queryset().mentioned()

    def unmentioned(self):
        return self.get_queryset().unmentioned()

    def mentioned_on_project(self, project):
        return self.get_queryset().mentioned_on_project(project)

    def unmentioned_on_project(self, project):
        return self.get_queryset().unmentioned_on_project(project)

    def mentioned_by_bot(self, bot):
        return self.get_queryset().mentioned_by_bot(bot)

    def unmentioned_by_bot(self, bot):
        return self.get_queryset().unmentioned_by_bot(bot)

    def mentioned_by_bot_on_project(self, *args):
        return self.get_queryset().mentioned_by_bot_on_project(*args)

    def saved_lte_days(self, days):
        return self.get_queryset().saved_lte_days(days)

    def not_followed(self):
        return self.get_queryset().not_followed()


class McTweetManager(MyManager):
    def put_checking_to_not_checking(self):
        if self.exists():
            self.filter(destination_bot_is_checking_mention=True).update(destination_bot_is_checking_mention=False)
            settings.LOGGER.info('All previous verifying mctweets were set to not verifying')


class FeedItemManager(MyManager):
    # querysets

    def get_queryset(self):
        return FeedItemQuerySet(self.model, using=self._db)

    def for_bot(self, bot):
        return self.get_queryset().for_bot(bot)

    def not_sent_by_bot(self, bot):
        return self.get_queryset().not_sent_by_bot(bot)

    def sent_by_bot(self, bot):
        return self.get_queryset().sent_by_bot(bot)
