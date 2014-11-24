import logging
from core.models import TwitterBot
from project.exceptions import FatalError
from twitter_bots import settings

settings.LOGGER = logging.getLogger(__name__)

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Creates bots'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED BOT CREATOR --')

        TwitterBot.objects.clean_unregistered()
        TwitterBot.objects.put_previous_being_created_to_false()

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
