import time
from project.models import Extractor
from project.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand

MODULE_NAME = __name__.split('.')[-1]


class Command(BaseCommand):
    help = 'Extract followers from all target users'

    def handle(self, *args, **options):
        set_logger(__name__)
        settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)

        num_loops = int(args[0]) if args else 1

        for _ in xrange(num_loops):
            try:
                Extractor.objects.extract_followers_for_running_projects()
            except Exception as e:
                if num_loops > 1:
                    settings.LOGGER.exception(e.message)
                else:
                    raise FatalError(e)
            finally:
                time.sleep(10)

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)