from core.models import TwitterBot, Proxy


from django.core.management.base import BaseCommand
from project.models import ProxiesGroup
from twitter_bots import settings
from twitter_bots.settings import set_logger


class Command(BaseCommand):

    def handle(self, *args, **options):
        set_logger(__name__)

        if args:
            group_to_check = ProxiesGroup.objects.get(name=args[0])
            # escogemos aquellos bots que tengan el
            bots_to_check = TwitterBot.objects.using_proxies_group(group_to_check)
            for bot in bots_to_check:
                bot.check_proxy_ok()
        else:
            settings.LOGGER.error('You must enter a group to check proxies')