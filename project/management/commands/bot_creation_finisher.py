from optparse import make_option
from core.models import TwitterBot
from core.scrapper.utils import get_2_args
from project.exceptions import FatalError
from project.models import Tweet
from twitter_bots import settings
from twitter_bots.settings import set_logger

set_logger(__name__)

from django.core.management.base import BaseCommand

settings.TAKE_SCREENSHOTS = True

class Command(BaseCommand):
    help = 'Finish pendant tasks to finish bot creation'

    option_list = BaseCommand.option_list + (
        make_option('--bot',
            dest='bot',
            help='Finish creation only for given bot'),
        )

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED BOT CREATION FINISHER --')

        num_threads, num_tasks = get_2_args(args)
        bot = options.get('bot', None)

        try:
            TwitterBot.objects.finish_creations(num_threads=num_threads, num_tasks=num_tasks, bot=bot)
        except Exception as e:
            raise FatalError(e)

        settings.LOGGER.info('-- FINISHED BOT CREATION FINISHER --')
