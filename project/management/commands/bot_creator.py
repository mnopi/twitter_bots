import copy
from core.models import TwitterBot
from twitter_bots import settings
from twitter_bots.settings import set_logger

LOGGING = set_logger('bot_creator')

from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Creates bots'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED BOT CREATOR --')

        TwitterBot.objects.clean_unregistered_bots()

        if args and '1' in args:
            TwitterBot.objects.create_bot()
        else:
            TwitterBot.objects.create_bots()

        settings.LOGGER.info('-- FINISHED BOT CREATOR --')
