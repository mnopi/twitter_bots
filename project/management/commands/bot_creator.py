from optparse import make_option
from threading import Lock
import threading
from core.models import TwitterBot, Proxy
from core.scrapper.utils import get_th_tasks
from project.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger

set_logger(__name__)

# forzamos a que siempre tome las capturas
settings.TAKE_SCREENSHOTS = True

mutex = Lock()

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

        try:
            num_threads, num_tasks = get_th_tasks(args)
            TwitterBot.objects.create_bots(num_threads=num_threads, num_tasks=num_tasks)
        except Exception as e:
            raise FatalError(e)

        settings.LOGGER.info('-- FINISHED BOT CREATOR --')
