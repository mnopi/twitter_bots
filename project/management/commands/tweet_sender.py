import multiprocessing
import os
from core.models import TwitterBot
from project.models import Tweet
from project.exceptions import FatalError
from twitter_bots import settings
import time

__author__ = 'Michel'

MODULE_NAME = __name__.split('.')[-1]

from django.core.management.base import BaseCommand, CommandError

settings.set_logger(MODULE_NAME)

class Command(BaseCommand):
    help = 'Send pending tweets'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)

        Tweet.objects.put_sending_to_not_sending()

        try:
            if args and '1' in args:
                TwitterBot.objects.send_tweet_from_pending_queue()
            else:
                TwitterBot.objects.send_pending_tweets()
        except Exception:
            raise FatalError()

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)

