from twitter_bots.settings import LOGGER

__author__ = 'Michel'


class RateLimitedException(Exception):
    def __init__(self):
        LOGGER.warning('Rate limit exceeded getting from twitter API')