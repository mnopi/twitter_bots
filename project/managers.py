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
    FeedItemQuerySet
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

    def get_mention_ready_to_send(self, bot=None):
        """Mira en la cola de menciones por enviar a usuarios de twitter y devuelve una que se pueda enviar.
        Todo este método se ejecuta en exclusión mutua"""

        settings.LOGGER.debug('Getting mention ready to send..')

        pending_mentions = self.get_queued_twitteruser_mentions_to_send(by_bot=bot)\
            .select_related('bot_used').select_related('bot_used__proxy_for_usage__proxies_group')
        if pending_mentions.exists():
            mention_ready_to_send = None

            for mention in pending_mentions:
                try:
                    mention.check_if_can_be_sent()
                    mention.sending = True
                    mention.save()
                    mention_ready_to_send = mention
                    break
                except (TweetConstructionError,
                        BotIsAlreadyBeingUsed,
                        BotHasNotEnoughTimePassedToTweetAgain):
                    continue

                except BotHasReachedConsecutiveTUMentions as e:
                    mctweet_sender_bot = e.bot
                    mctweet = mctweet_sender_bot.get_or_create_mctweet()

                    if mctweet.sent_ok:
                        try:
                            mctweet.check_if_can_be_verified()
                            mctweet.tweet_checking_mention.destination_bot_is_checking_mention = True
                            mctweet.tweet_checking_mention.save()
                            raise McTweetMustBeVerified(mctweet)
                        except (TweetConstructionError,
                                DestinationBotIsBeingUsed,
                                VerificationTimeWindowNotPassed,
                                SentOkMcTweetWithoutDateSent):
                            continue
                    else:
                        try:
                            mctweet_sender_bot.check_if_can_send_mctweet()
                            mctweet.sending = True
                            mctweet.save()
                            raise McTweetMustBeSent(mctweet)
                        except LastMctweetFailedTimeWindowNotPassed:
                            continue

                except MuTweetHasNotSentFTweetsEnough as e:
                    ftweet = e.mutweet.get_or_create_ftweet_to_send()
                    ftweet.sending = True
                    ftweet.save()
                    raise FTweetMustBeSent(ftweet)

                except SenderBotHasToFollowPeople as e:
                    e.sender_bot.is_following = True
                    e.sender_bot.save()
                    # marcamos los twitterusers a seguir por el bot
                    e.sender_bot.mark_twitterusers_to_follow_at_once()
                    raise e

                except Exception as e:
                    settings.LOGGER.error('Error getting tumention from queue for bot %s: %s' %
                                          (mention.bot_used.username, mention.compose()))
                    raise e

            if mention_ready_to_send:
                return mention_ready_to_send
            else:
                # por si se eliminaron tweets mal construídos volvemos a comprobar si la cola está o no vacía
                if not self.get_queued_twitteruser_mentions_to_send():
                    raise EmptyMentionQueue(bot=bot)
                elif bot:
                    raise NoAvailableBot(bot)
                else:
                    raise NoAvailableBots
        else:
            raise EmptyMentionQueue(bot=bot)

    def create_mentions_to_send(self):
        """Crea los tweets a encolar para cada bot disponible"""

        from project.models import Project
        from core.models import TwitterBot

        running_projects = Project.objects.running()
        if running_projects.exists():
            settings.LOGGER.info('Creating tweets for running project(s): %s' %
                                 Project.objects.get_names_list(running_projects))

            # dentro de los proyectos en ejecución tomamos sus bots
            bots_in_running_projects = TwitterBot.objects.usable_regardless_of_proxy()\
                .using_in_running_projects()\
                .with_proxy_connecting_ok()

            # comprobamos sus proxies si siguen funcionando
            TwitterBot.objects.check_proxies(bots_in_running_projects)

            bots_with_free_queue = bots_in_running_projects.without_tweet_to_send_queue_full()
            if bots_with_free_queue.exists():
                for bot in bots_with_free_queue:
                    bot.make_mutweet_to_send()
            else:
                if bots_in_running_projects:
                    settings.LOGGER.info('Mention to send queue full for all twitteable bots at this moment. Waiting %d seconds..'
                                         % settings.TIME_WAITING_FREE_QUEUE)
                    time.sleep(settings.TIME_WAITING_FREE_QUEUE)
                else:
                    settings.LOGGER.error('No twitteable bots available for running projects. Waiting %d seconds..'
                                          % settings.TIME_WAITING_NEW_TWITTEABLE_BOTS)
        else:
            settings.LOGGER.warning('No projects running at this moment')

    def get_queued_twitteruser_mentions_to_send(self, by_bot=None):
        """Devuelve los tweets encolados pendientes de enviar a los twitter users. Si salen varios tweets por bots
        dejamos sólo 1 por bot, ya que no puede enviar varios a la vez"""

        queue = self.raw_as_qs("""
            select
                project_tweet.id,
                core_twitterbot.id,

                #
                # sender sending
                #
                (select count(project_tweet.id) > 0 AS sender_already_sending
                    from project_tweet where project_tweet.sending=True and project_tweet.bot_used_id = core_twitterbot.id
                ) as sender_already_sending,

                #
                # sender verifying
                #
                (select count(project_tweetcheckingmention.id) > 0 AS sender_verifying
                    from project_tweet
                    left outer join project_tweet_mentioned_bots on project_tweet.id = project_tweet_mentioned_bots.tweet_id
                    left outer join project_tweetcheckingmention ON project_tweet.id = project_tweetcheckingmention.tweet_id
                    where
                    project_tweet_mentioned_bots.twitterbot_id = core_twitterbot.id
                    and project_tweetcheckingmention.destination_bot_is_checking_mention = True
                ) as sender_verifying,

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
                and core_twitterbot.is_following=False

            group by core_twitterbot.id

            having
                sender_already_sending = False
                and sender_verifying = False
                and timewindow_passed = True
        """
        )

        if by_bot:
            queue = queue.by_bot(by_bot)

        return queue

    def clean_not_ok(self):
        from project.models import TweetCheckingMention

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
            settings.LOGGER.info('Tweet queue empty' % count)

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
    def display_extractor_mode(self, mode):
        from .models import Extractor
        if mode == Extractor.FOLLOWER_MODE:
            return 'follower'
        elif mode == Extractor.HASHTAG_MODE:
            return 'hashtag'

    def log_extractor_being_used(self, extractor, mode):
        settings.LOGGER.debug('### Using %s extractor: %s behind proxy %s ###' %
                             (self.display_extractor_mode(mode),
                              extractor.twitter_bot.username,
                              extractor.twitter_bot.proxy_for_usage.__unicode__()))

    def extract_followers_for_running_projects(self):
        """Tienen prioridad los targetusers cuyos proyectos tengan menos usuarios por mencionar"""
        from project.models import TargetUser, Project, TwitterUser

        # limpiamos los antiguos todavía sin mencionar
        TwitterUser.objects.clear_old_unmentioned()

        # vamos iterando por cada uno de los proyectos en ejecución
        running_projects = Project.objects.filter(is_running=True)
        if running_projects.exists():
            for project in running_projects:
                try:
                    project.check_if_full_of_unmentioned_twitterusers()
                except ProjectFullOfUnmentionedTwitterusers:
                    continue
                else:
                    project_targetusers = TargetUser.objects.for_project(project)
                    if project_targetusers.exists():
                        # sacamos el targetuser con última extracción, poniendo delante los que no se extrajeron nunca
                        targetusers_available_to_extract = project_targetusers\
                            .available_to_extract()\
                            .extra(select={'date_le_null': 'date_last_extraction IS NULL',})\
                            .order_by('date_last_extraction', 'date_le_null')
                        if targetusers_available_to_extract.exists():
                            # tu = targetusers_available_to_extract.filter(next_cursor__isnull=True).order_by('?').first()
                            # self.extract_followers_from_tu(tu)
                            self.extract_followers_from_tu(targetusers_available_to_extract.first())
                        else:
                            settings.LOGGER.warning('Project "%s" has all targetusers extracted' % project.name)
                    else:
                        settings.LOGGER.warning('Project "%s" has no target users added!' % project.name)
        else:
            raise NoRunningProjects

        settings.LOGGER.debug('sleeping 20 seconds..')
        time.sleep(20)

    def extract_followers_from_tu(self, target_user):
        from project.models import Extractor, Project

        available_follower_extractors = self.available(Extractor.FOLLOWER_MODE)
        if available_follower_extractors.exists():
            settings.LOGGER.info('Extracting followers from targetuser: %s (project(s): %s)' %
                                 (target_user.username, Project.objects.get_names_list(target_user.get_projects())))
            for extractor in available_follower_extractors:
                try:
                    self.log_extractor_being_used(extractor, mode=Extractor.FOLLOWER_MODE)
                    extractor.connect_twitter_api()
                    extractor.extract_followers_from_tuser(target_user)
                except TweepError as e:
                    if 'Cannot connect to proxy' in e.reason:
                        settings.LOGGER.exception('Extractor %s can\'t connect to proxy %s' %
                                                  (extractor.twitter_bot.username,
                                                   extractor.twitter_bot.proxy_for_usage.__unicode__()))
                        continue
                    else:
                        raise e
                except (AllFollowersExtracted,
                        ExtractorReachedMaxConsecutivePagesRetrievedPerTUser,
                        TargetUserWasSuspended):
                    break
                except (RateLimitedException,
                        InternetConnectionError):
                    continue
        else:
            settings.LOGGER.error('No available follower extractors. Sleeping..')
            time.sleep(30)

    def extract_hashtags(self):
        from .models import Extractor
        for extractor in self.get_available_extractors(Extractor.HASHTAG_MODE):
            try:
                self.log_extractor_being_used(extractor, mode=Extractor.HASHTAG_MODE)
                extractor.extract_twitter_users_from_all_hashtags()
            except TweepError as e:
                if 'Cannot connect to proxy' in e.reason:
                    settings.LOGGER.exception('')
                    continue
                else:
                    raise e
            except RateLimitedException:
                continue

        time.sleep(random.randint(5, 15))

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
        old_unmentioned = self.unmentioned().saved_lte_days(settings.MAX_DAYS_TO_STAY_UNMENTIONED)
        count = old_unmentioned.count()
        old_unmentioned.delete()
        if count > 0:
            settings.LOGGER.info('Deleted %i old unmentioned twitterusers' % count)

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
