from core.models import TwitterBot
from project.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger

set_logger(__name__)

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
        except Exception as e:
            raise FatalError(e)

        settings.LOGGER.info('-- FINISHED BOT CREATOR --')
