from core.models import TwitterBot, Proxy


from django.core.management.base import BaseCommand
from project.models import ProxiesGroup, Tweet, TwitterUser
from twitter_bots import settings
from twitter_bots.settings import set_logger


class Command(BaseCommand):

    def handle(self, *args, **options):
        set_logger(__name__)

        TwitterUser.objects.clear_all_unmentioned()
