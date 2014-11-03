import copy
from core.models import TwitterBot, Proxy
from twitter_bots import settings
from twitter_bots.settings import set_logger

set_logger('sync_proxies')

from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = """
        Sincroniza la lista de proxies actuales en los proxies/*.txt con nuestra tabla proxy en BD.

        IMPORTANTE: ejecutar esto cada vez que se cambien los .txt !!
        """

    def handle(self, *args, **options):
        Proxy.objects.sync_proxies()