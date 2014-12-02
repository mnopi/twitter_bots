from core.models import TwitterBot
from project.models import Tweet
from project.exceptions import FatalError
from twitter_bots import settings
from django.core.management.base import BaseCommand
from twitter_bots.settings import set_logger


MODULE_NAME = __name__.split('.')[-1]


class Command(BaseCommand):
    help = 'Send pending tweets'

    def handle(self, *args, **options):
        set_logger(__name__)
        settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)

        try:
            Tweet.objects.put_sending_to_not_sending()

            if args and '1' in args:
                TwitterBot.objects.send_tweet_from_pending_queue()
            else:
                TwitterBot.objects.send_pending_tweets()
        except Exception:
            raise FatalError()

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)

