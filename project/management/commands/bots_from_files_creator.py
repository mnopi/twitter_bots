from core.models import Proxy, TwitterBot
from twitter_bots import settings
from twitter_bots.settings import set_logger

MODULE_NAME = __name__.split('.')[-1]

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = """
        Crea bots a partir de los indicados en la carpeta core/bots
        """

    def handle(self, *args, **options):
        set_logger(__name__)
        settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)
        TwitterBot.objects.create_bots_from_files()
        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)
