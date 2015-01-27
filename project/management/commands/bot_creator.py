from optparse import make_option
from threading import Lock
import threading
from core.models import TwitterBot, Proxy
from project.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger

set_logger(__name__)
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
            threads = []
            if settings.EXTRACT_FOLLOWERS:
                threads.append(threading.Thread(target=Extractor.objects.extract_followers_for_running_projects))
            # if settings.EXTRACT_HASHTAGS:
                # threads.append(threading.Thread(target=Extractor.objects.extract_hashtags))
            for th in threads:
                th.start()

            # to wait until all threads are finished
            for th in threads:
                th.join()


            num_bots = int(args[0]) if args else None
            TwitterBot.objects.create_bots(num_bots=num_bots)

            TwitterBot.objects.finish_creations(num_bots=num_bots)
        except Exception as e:
            raise FatalError(e)

        settings.LOGGER.info('-- FINISHED BOT CREATOR --')
