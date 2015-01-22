from optparse import make_option
from core.models import TwitterBot
from project.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger

set_logger(__name__)
settings.TAKE_SCREENSHOTS = True

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Creates bots'

    option_list = BaseCommand.option_list + (
        make_option('--dyn',
            dest='dyn',
            action='store_true',
            help='Create bots from dynamic ip resetting router all the time'),
        )

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED BOT CREATOR --')

        TwitterBot.objects.clean_unregistered()
        TwitterBot.objects.put_previous_being_created_to_false()

        try:
            if args and '1' in args:
                TwitterBot.objects.create_bot('dyn' in options)
            else:
                if args:
                    TwitterBot.objects.create_bots(num_bots=int(args[0]), from_dyn_ip='dyn' in options)
                else:
                    TwitterBot.objects.create_bots(from_dyn_ip='dyn' in options)
        except Exception as e:
            raise FatalError(e)

        settings.LOGGER.info('-- FINISHED BOT CREATOR --')
