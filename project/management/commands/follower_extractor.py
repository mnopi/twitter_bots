import copy
from project.models import Project
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand, CommandError

set_logger('follower_extractor')
from twitter_bots.settings import LOGGER

class Command(BaseCommand):
    help = 'Creates bots'

    def handle(self, *args, **options):
        LOGGER.info('-- Initialized follower extractor --')
        for project in Project.objects.all():
            LOGGER.info('Extracting followers for all target users in project "%s"' % project.name)
            project.extract_followers_from_all_target_users()

