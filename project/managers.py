# -*- coding: utf-8 -*-

import time
import random
from tweepy import TweepError
from core.managers import MyManager
from project.exceptions import RateLimitedException, AllFollowersExtracted, AllBotsInUse, \
    NoTweetsOnQueue
from project.querysets import ProjectQuerySet, TwitterUserQuerySet, TweetQuerySet, ExtractorQuerySet, TargetUserQuerySet
from scrapper.utils import get_thread_name, is_lte_than_seconds_ago
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


class TweetManager(models.Manager):
    def all_sent_ok(self):
        "Devuelve si en BD todos los tweets están marcados como enviados"
        return self.get_sent_ok().count() == self.all().count()

    def clean_not_sent_ok(self):
        self.filter(sent_ok=False).delete()
        settings.LOGGER.info('Deleted previous sending tweets')

    def put_sending_to_not_sending(self):
        if self.exists():
            self.filter(sending=True).update(sending=False)
            settings.LOGGER.info('All previous sending tweets were set to not sending')

    def get_tweet_ready_to_send(self):
        """Saca de la cola los tweets que se puedan enviar
            -   los que su robot no esté actualmente enviando tweet
            -   los que su robot haya tuiteado por última hace x minutos

        Se queda esperando a que
        """
        try:
            pending_tweets = self.queued_to_send()

            if pending_tweets:
                for tweet in pending_tweets:
                    if tweet.can_be_sent():
                        return tweet

                raise AllBotsInUse
            else:
                raise NoTweetsOnQueue
        except Exception as e:
            if type(e) is AllBotsInUse or type(e) is NoTweetsOnQueue:
                self.get_tweet_ready_to_send()
            else:
                settings.LOGGER.exception('%s Error getting tweet available to send' % get_thread_name())
                raise e

    def create_tweets_to_send(self):
        """Crea los tweets a encolar para cada bot disponible"""
        from project.models import Project
        from core.models import TwitterBot

        if Project.objects.running().exists():
            # dentro de los proyectos en ejecución tomamos sus bots
            bots_in_running_projects = TwitterBot.objects.twitteable().using_in_running_projects()
            bots_with_free_queue = bots_in_running_projects.without_tweet_to_send_queue_full()
            if bots_with_free_queue.exists():
                for bot in bots_with_free_queue:
                    bot.make_tweet_to_send()
            else:
                if bots_in_running_projects:
                    settings.LOGGER.info('Tweet to send queue full for all twitteable bots at this moment. Waiting %d seconds..'
                                         % settings.TIME_WAITING_FREE_QUEUE)
                    time.sleep(settings.TIME_WAITING_FREE_QUEUE)
                else:
                    settings.LOGGER.error('No twitteable bots available for running projects. Waiting %d seconds..'
                                          % settings.TIME_WAITING_NEW_TWITTEABLE_BOTS)
        else:
            settings.LOGGER.warning('No projects running at this moment')

    #
    # proxy queryset methods
    #

    def get_queryset(self):
        return TweetQuerySet(self.model, using=self._db)

    def sent_ok(self):
        return self.get_queryset().sent_ok()

    def queued_to_send(self):
        return self.get_queryset().queued_to_send()


class ProjectManager(models.Manager):
    #
    # PROXY QS
    #
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
        settings.LOGGER.info('### Using %s extractor: %s behind proxy %s ###' %
                             (self.display_extractor_mode(mode),
                              extractor.twitter_bot.username,
                              extractor.twitter_bot.proxy_for_usage.__unicode__()))

    def extract_followers(self):
        from project.models import Extractor

        available_follower_extractors = self.available(Extractor.FOLLOWER_MODE)
        if available_follower_extractors.exists():
            for extractor in available_follower_extractors:
                try:
                    self.log_extractor_being_used(extractor, mode=Extractor.FOLLOWER_MODE)
                    extractor.extract_followers_from_all_target_users()
                except TweepError as e:
                    if 'Cannot connect to proxy' in e.reason:
                        settings.LOGGER.exception('')
                        continue
                    else:
                        raise e
                except AllFollowersExtracted:
                    break
                except RateLimitedException:
                    continue

            time.sleep(random.randint(5, 15))
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
    def log_groups_with_creation_disabled(self):
        groups_with_creation_disabled = self.filter(is_bot_creation_enabled=False)
        if groups_with_creation_disabled.exists():
            groups_str = ', '.join([group.name for group in groups_with_creation_disabled])
            settings.LOGGER.warning('There are %d groups that have bot creation disabled: %s' %
                                    (groups_with_creation_disabled.count(), groups_str))

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
            SELECT total_project_users.id
            FROM
                (
                    (
                        select project_twitteruser.id, project_twitteruser.last_tweet_date
                        %(language_field)s
                        from project_twitteruser
                        LEFT OUTER JOIN project_follower ON (project_twitteruser.id = project_follower.twitter_user_id)
                        LEFT OUTER JOIN project_targetuser ON (project_follower.target_user_id = project_targetuser.id)
                        LEFT OUTER JOIN project_project_target_users ON (project_targetuser.id = project_project_target_users.targetuser_id)
                        WHERE project_project_target_users.project_id = %(project_pk)d
                    )
                    union
                    (
                        select project_twitteruser.id, project_twitteruser.last_tweet_date
                        %(language_field)s
                        from project_twitteruser
                        LEFT OUTER JOIN project_twitteruserhashashtag ON (project_twitteruser.id = project_twitteruserhashashtag.twitter_user_id)
                        LEFT OUTER JOIN project_hashtag ON (project_twitteruserhashashtag.hashtag_id = project_hashtag.id)
                        LEFT OUTER JOIN project_project_hashtags ON (project_hashtag.id = project_project_hashtags.hashtag_id)
                        WHERE project_project_hashtags.project_id = %(project_pk)d
                    )
                    union
                    (
						select project_twitteruser.id, project_twitteruser.last_tweet_date
						%(language_field)s
						from project_twitteruser
						LEFT OUTER JOIN project_follower ON (project_twitteruser.id = project_follower.twitter_user_id)
						LEFT OUTER JOIN project_targetuser ON (project_follower.target_user_id = project_targetuser.id)
						LEFT OUTER JOIN project_tugroup_target_users ON (project_targetuser.id = project_tugroup_target_users.targetuser_id)
						LEFT OUTER JOIN project_tugroup ON (project_tugroup_target_users.tugroup_id = project_tugroup.id)
						LEFT OUTER JOIN project_project_tu_group ON (project_tugroup.id = project_project_tu_group.tugroup_id)
						WHERE project_project_tu_group.project_id = %(project_pk)d
                    )
                    union
                    (
						select project_twitteruser.id, project_twitteruser.last_tweet_date
						%(language_field)s
						from project_twitteruser
						LEFT OUTER JOIN project_twitteruserhashashtag ON (project_twitteruser.id = project_twitteruserhashashtag.twitter_user_id)
						LEFT OUTER JOIN project_hashtag ON (project_twitteruserhashashtag.hashtag_id = project_hashtag.id)
						LEFT OUTER JOIN project_hashtaggroup_hashtags ON (project_hashtag.id = project_hashtaggroup_hashtags.hashtag_id)
						LEFT OUTER JOIN project_hashtaggroup ON (project_hashtaggroup_hashtags.hashtaggroup_id = project_hashtaggroup.id)
						LEFT OUTER JOIN project_project_hashtag_group ON (project_hashtaggroup.id = project_project_hashtag_group.hashtaggroup_id)
						WHERE project_project_hashtag_group.project_id = %(project_pk)d
                    )
                ) total_project_users
            LEFT OUTER JOIN project_tweet_mentioned_users ON (total_project_users.id = project_tweet_mentioned_users.twitteruser_id)
            WHERE project_tweet_mentioned_users.tweet_id IS NULL
            %(language)s
            ORDER BY total_project_users.last_tweet_date DESC
            %(limit)s
            """ %
            {
                'project_pk': project.pk,
                'limit': 'LIMIT %d' % limit if limit else '',
                'language': 'and total_project_users.language="%s"' % language if language else '',
                'language_field': ', project_twitteruser.language' if language else ''
            }
        )

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