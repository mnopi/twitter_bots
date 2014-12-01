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

        try:
            Extractor.objects.extract_followers()
        except Exception:
            raise FatalError()

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)