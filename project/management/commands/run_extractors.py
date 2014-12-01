import copy
import random
from threading import Lock
import threading
from project.models import Extractor
from project.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand

mutex = Lock()

class Command(BaseCommand):
    help = 'Extract followers from all target users'

    def handle(self, *args, **options):
        set_logger(__name__)

        settings.LOGGER.info('-- INITIALIZED run_extractors --')

        try:
            threads = []
            if settings.EXTRACT_FOLLOWERS:
                threads.append(threading.Thread(target=Extractor.objects.extract_followers))
            # if settings.EXTRACT_HASHTAGS:
                # threads.append(threading.Thread(target=Extractor.objects.extract_hashtags))
            for th in threads:
                th.start()

            # to wait until all threads are finished
            for th in threads:
                th.join()
        except Exception:
            raise FatalError()

        settings.LOGGER.info('-- FINISHED run_extractors --')