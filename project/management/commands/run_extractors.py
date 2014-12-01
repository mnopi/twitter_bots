import copy
import random
from threading import Lock
import threading
import time
from project.exceptions import RateLimitedException
from project.models import Project, TargetUser, Extractor
from project.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand, CommandError

set_logger('run_extractors')

mutex = Lock()

class Command(BaseCommand):
    help = 'Extract followers from all target users'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED run_extractors --')

        try:
            threads = []
            if settings.EXTRACT_FOLLOWERS:
                threads.append(threading.Thread(target=Extractor.objects.extract_followers))
            # if settings.EXTRACT_HASHTAGS:
            #     threads.append(threading.Thread(target=Extractor.objects.extract_hashtags))
            for th in threads:
                th.start()

            # to wait until all threads are finished
            for th in threads:
                th.join()
        except Exception:
            raise FatalError()

        settings.LOGGER.info('-- FINISHED run_extractors --')