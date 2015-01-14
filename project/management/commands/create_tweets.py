import time
from project.exceptions import TwitteableBotsNotFound, NoAvailableProxiesToAssignBotsForUse
from project.models import Tweet
from project.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand

MODULE_NAME = __name__.split('.')[-1]


class Command(BaseCommand):
    help = 'Make tweets to send by tweet_sender'

    def handle(self, *args, **options):
        set_logger(__name__)
        settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)

        try:
            Tweet.objects.create_mentions_to_send()
        except (NoAvailableProxiesToAssignBotsForUse,
                TwitteableBotsNotFound):
            pass
        except Exception as e:
            raise FatalError(e)
        finally:
            time.sleep(10)

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)