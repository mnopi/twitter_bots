import threading
import datetime
from scrapper.utils import get_thread_name
from twitter_bots import settings
import time

__author__ = 'Michel'


class RateLimitedException(Exception):
    def __init__(self, extractor):
        settings.LOGGER.warning('Rate limited exceeded for extractor %s' % extractor.twitter_bot.username)
        extractor.is_rate_limited = True
        extractor.save()


class AllFollowersExtracted(Exception):
    def __init__(self):
        settings.LOGGER.warning('All followers were extracted from all active target_users in all active projects')
        time.sleep(20)


class AllHashtagsExtracted(Exception):
    def __init__(self):
        settings.LOGGER.warning('All hashtags were extracted from all active hashtags in all active projects')
        time.sleep(20)


class TwitteableBotsNotFound(Exception):
    def __init__(self):
        settings.LOGGER.warning('%s Bots not found to mention any user' % get_thread_name())
        time.sleep(10)


class AllBotsInUse(Exception):
    def __init__(self):
        settings.LOGGER.warning('%s All bots in use. Retrying in %i seconds' %
                                (get_thread_name(), settings.TIME_WAITING_AVAIABLE_BOT_TO_TWEET))
        time.sleep(settings.TIME_WAITING_AVAIABLE_BOT_TO_TWEET)


class NoTweetsOnQueue(Exception):
    def __init__(self):
        settings.LOGGER.warning('%s No tweets on queue. Retrying in %s seconds' %
                                (get_thread_name(), settings.TIME_WAITING_AVAIABLE_BOT_TO_TWEET))
        time.sleep(settings.TIME_WAITING_AVAIABLE_BOT_TO_TWEET)
