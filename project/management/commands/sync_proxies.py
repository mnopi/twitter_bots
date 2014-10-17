import copy
from core.models import TwitterBot, Proxy
from twitter_bots import settings
from twitter_bots.settings import set_logger

set_logger('sync_proxies')

from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Creates bots'

    def handle(self, *args, **options):
        Proxy.objects.sync_proxies()