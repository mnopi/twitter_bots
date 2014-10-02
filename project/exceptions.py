import threading
from twitter_bots import settings

__author__ = 'Michel'


class RateLimitedException(Exception):
    def __init__(self, extractor):
        settings.LOGGER.warning('Rate limited exceeded for extractor %s' % extractor.twitter_bot.username)


class BotNotFoundException(Exception):
    def __init__(self):
        settings.LOGGER.warning('###%s### - Bot not found to mention any user' % threading.current_thread().name)