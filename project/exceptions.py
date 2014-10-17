import threading
import datetime
from twitter_bots import settings
import time

__author__ = 'Michel'


class RateLimitedException(Exception):
    def __init__(self, extractor):
        settings.LOGGER.warning('Rate limited exceeded for extractor %s' % extractor.twitter_bot.username)
        extractor.is_rate_limited = True
        extractor.save()


class BotsWithTweetNotFoundException(Exception):
    def __init__(self):
        settings.LOGGER.warning('###%s### - Bots not found to mention any user' % threading.current_thread().name)
        time.sleep(10)