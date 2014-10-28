import copy
import random
from threading import Lock
import threading
import time
from project.exceptions import RateLimitedException, TwitteableBotsNotFound
from project.models import Project, TargetUser, Extractor, Tweet
from scrapper.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand, CommandError

MODULE_NAME = __name__.split('.')[-1]

set_logger(MODULE_NAME)

MAX_PENDING_TWEETS = settings.MAX_THREADS_SENDING_TWEETS * 2


class Command(BaseCommand):
    help = 'Make tweets to send by tweet_sender'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)

        try:
            Tweet.objects.create_tweets_to_send()
            time.sleep(10)
        except Exception as e:
            if type(e) is not TwitteableBotsNotFound:
                raise FatalError()

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)