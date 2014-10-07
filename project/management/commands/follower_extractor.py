import copy
import random
import time
from project.exceptions import RateLimitedException
from project.models import Project, TargetUser, Extractor
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand, CommandError

set_logger('follower_extractor')

class Command(BaseCommand):
    help = 'Extract followers from all target users'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED follower extractor --')
        extractors = Extractor.objects.all()
        for extractor in extractors:
            if extractor.is_available():
                try:
                    settings.LOGGER.info('### Using extractor: %s @ %s - %s###' %
                                         (extractor.twitter_bot.username,
                                          extractor.twitter_bot.proxy.proxy,
                                          extractor.twitter_bot.proxy.proxy_provider))
                    extractor.extract_followers_from_all_target_users()
                except RateLimitedException:
                    continue

        time.sleep(random.randint(5, 15))
        settings.LOGGER.info('-- FINISHED follower extractor --')