import copy
from core.models import TwitterBot, Proxy
from scrapper.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger

set_logger('bot_creator')

from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Creates bots'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED BOT CREATOR --')

        try:
            if args and '1' in args:
                TwitterBot.objects.create_bot()
            else:
                if args:
                    TwitterBot.objects.create_bots(num_bots=int(args[0]))
                else:
                    TwitterBot.objects.create_bots()
        except Exception:
            raise FatalError()

        settings.LOGGER.info('-- FINISHED BOT CREATOR --')
