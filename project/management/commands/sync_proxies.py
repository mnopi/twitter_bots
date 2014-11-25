from core.models import Proxy
from twitter_bots import settings
from twitter_bots.settings import set_logger

set_logger(__name__)

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = """
        Sincroniza la lista de proxies actuales en los proxies/*.txt con nuestra tabla proxy en BD.

        IMPORTANTE: ejecutar esto cada vez que se cambien los .txt !!
        """

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED SYNC PROXIES --')
        Proxy.objects.sync_proxies()
        settings.LOGGER.info('-- FINISHED SYNC PROXIES --')
