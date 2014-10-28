# -*- coding: utf-8 -*-

import time
import random
import datetime
from django.db.models import Count
import pytz
from tweepy import TweepError
from core.models import TwitterBot
from project.exceptions import RateLimitedException, AllFollowersExtracted, TwitteableBotsNotFound, AllBotsInUse, \
    NoTweetsOnQueue
from scrapper.utils import get_thread_name
from twitter_bots import settings
from django.db import models


class TargetUserManager(models.Manager):
    def create(self, **kwargs):
        target_user_created = super(TargetUserManager, self).create(**kwargs)
        target_user_created.complete_creation()

    def get_available_to_extract(self):
        return self.filter(is_active=True, projects__is_running=True).exclude(next_cursor=None)


class TweetManager(models.Manager):
    def get_sent_ok(self):
        return self.filter(sent_ok=True)

    def all_sent_ok(self):
        return self.get_sent_ok().count() == self.all().count()

    def clean_not_sent_ok(self):
        self.filter(sent_ok=False).delete()
        settings.LOGGER.info('Deleted previous sending tweets')

    def put_sending_to_not_sending(self):
        self.filter(sending=True).update(sending=False)
        settings.LOGGER.info('All previous sending tweets were set to not sending')

    def get_queued_to_send(self):
        return self.filter(sending=False, sent_ok=False)

    def get_tweet_ready_to_send(self):
        """Saca de la cola los tweets que se puedan enviar
            -   los que su robot no esté actualmente enviando tweet
            -   los que su robot haya tuiteado por última hace x minutos

        Se queda esperando a que
        """
        try:
            now_utc = datetime.datetime.now().replace(tzinfo=pytz.utc)
            random_seconds = random.randint(60*settings.TIME_BETWEEN_TWEETS[0], 60*settings.TIME_BETWEEN_TWEETS[1])  # entre 2 y 7 minutos por tweet
            min_datetime_to_tweet = now_utc - datetime.timedelta(seconds=random_seconds)

            pending_tweets = self.get_queued_to_send()

            if pending_tweets:
                for tweet in pending_tweets:
                    if not tweet.has_bot_sending_another():
                        last_tweet_sent = self.filter(bot_used=tweet.bot_used).latest('date_sent')
                        if not last_tweet_sent or not last_tweet_sent.date_sent or \
                            last_tweet_sent.date_sent <= min_datetime_to_tweet:
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
        twitteable_bots = TwitterBot.objects.get_all_twitteable_bots().all()

        if twitteable_bots:
            for bot in twitteable_bots:
                bot.make_mention_tweet_to_send()
        else:
            raise TwitteableBotsNotFound


class ProjectManager(models.Manager):
    def get_pending_to_process(self):
        "Devuelve todos los proyectos activos que tengan followers por mencionar"
        return self\
            .filter(running=True)\
            .annotate(unmentioned_users_count=Count('target_users__followers__twitter_user__mentions'))\
            .filter(unmentioned_users_count__gt=0)


class ExtractorManager(models.Manager):
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
                              extractor.twitter_bot.proxy.__unicode__()))

    def get_available_extractors(self, mode):

        available_extractors = [
            extractor for extractor in self.filter(mode=mode) if extractor.is_available()
        ]

        if not available_extractors:
            last_used_extractor = self.latest('last_request_date')
            settings.LOGGER.warning('No available %s extractors at this moment. Last used was %s at %s' %
                                    (self.display_extractor_mode(mode), last_used_extractor.twitter_bot.username,
                                     last_used_extractor.last_request_date))
        return available_extractors

    def extract_followers(self):
        from .models import Extractor
        for extractor in self.get_available_extractors(Extractor.FOLLOWER_MODE):
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