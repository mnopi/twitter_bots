import copy
import random
import time
from project.exceptions import RateLimitedException
from project.models import Project, TargetUser, Extractor
from core.scrapper.exceptions import FatalError
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand, CommandError

set_logger('hashtag_extractor')

class Command(BaseCommand):
    help = 'Extract twitter users from all hashtags to track'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED hashtag extractor --')

        try:
            Extractor.objects.extract_hashtags()
        except Exception:
            raise FatalError()

        settings.LOGGER.info('-- FINISHED hashtag extractor --')