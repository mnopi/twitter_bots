import copy
from core.models import TwitterBot, Proxy
from scrapper.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger

set_logger('bot_creation_finisher')

from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Finish pendant tasks to finish bot creation'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED BOT CREATION FINISHER --')

        try:
            TwitterBot.objects.complete_pendant_bot_creations()
        except Exception:
            raise FatalError()

        settings.LOGGER.info('-- FINISHED BOT CREATION FINISHER --')
