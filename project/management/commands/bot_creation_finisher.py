from core.models import TwitterBot
from project.exceptions import FatalError
import logging
from twitter_bots import settings

settings.LOGGER = logging.getLogger(__name__)

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Finish pendant tasks to finish bot creation'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED BOT CREATION FINISHER --')

        try:
            TwitterBot.objects.finish_creations()
        except Exception:
            raise FatalError()

        settings.LOGGER.info('-- FINISHED BOT CREATION FINISHER --')
