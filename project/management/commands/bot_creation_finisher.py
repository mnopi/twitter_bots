from core.models import TwitterBot
from project.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger

set_logger(__name__)

from django.core.management.base import BaseCommand

settings.TAKE_SCREENSHOTS = True

class Command(BaseCommand):
    help = 'Finish pendant tasks to finish bot creation'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED BOT CREATION FINISHER --')

        try:
            TwitterBot.objects.finish_creations()
        except Exception as e:
            raise FatalError(e)

        settings.LOGGER.info('-- FINISHED BOT CREATION FINISHER --')
