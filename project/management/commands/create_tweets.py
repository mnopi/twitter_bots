import time
from project.exceptions import TwitteableBotsNotFound
from project.models import Tweet
from project.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand

MODULE_NAME = __name__.split('.')[-1]

set_logger(__name__)


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