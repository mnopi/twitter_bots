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

            # vemos si el grupo tiene proxies que se puedan usar
            has_ok_proxies = group_to_check.proxies.connection_ok()
            if has_ok_proxies:
                # escogemos aquellos bots completamente creados que tenga el grupo
                bots_to_check = TwitterBot.objects.using_proxies_group(group_to_check).usable_regardless_of_proxy()
                if bots_to_check.exists():
                    for bot in bots_to_check:
                        bot.check_proxy_ok()
                else:
                    settings.LOGGER.error('Group %s has no completed bot' % group_to_check.name)
            else:
                settings.LOGGER.error('Group %s has no proxy ok. Assign them first and retry again' %
                                      group_to_check.name)
        else:
            settings.LOGGER.error('You must enter a group to check proxies')