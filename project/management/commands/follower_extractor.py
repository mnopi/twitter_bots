import copy
import random
import time
from project.exceptions import RateLimitedException
from project.models import Project, TargetUser, Extractor
from scrapper.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Extract followers from all target users'

    def handle(self, *args, **options):
        set_logger('follower_extractor')

        settings.LOGGER.info('-- INITIALIZED follower extractor --')

        try:
            Extractor.objects.extract_followers()
        except Exception:
            raise FatalError()

        settings.LOGGER.info('-- FINISHED follower extractor --')