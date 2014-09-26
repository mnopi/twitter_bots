import copy
import time
from project.models import Project
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand, CommandError

set_logger('follower_extractor')
from twitter_bots.settings import LOGGER

class Command(BaseCommand):
    help = 'Creates bots'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED follower extractor --')
        for project in Project.objects.all():
            project.extract_followers_from_all_target_users()
        settings.LOGGER.info('-- FINISHED follower extractor --')
        time.sleep(15)

