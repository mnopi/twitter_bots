from project.models import Project
from twitter_bots.settings import LOGGING

__author__ = 'Michel'


from django.core.management.base import BaseCommand, CommandError

F_E_LOGGING = LOGGING
F_E_LOGGING['handlers']['file']['filename'] = 'follower_extractor.log'
F_E_LOGGING['loggers']['follower_extractor'] = F_E_LOGGING['loggers']['twitter_bots']
del F_E_LOGGING['loggers']['twitter_bots']

import logging
LOGGING = logging.getLogger('follower_extractor')


class Command(BaseCommand):
    help = 'Creates bots'

    def handle(self, *args, **options):
        LOGGING.info('-- Initialized follower extractor --')
        for project in Project.objects.all():
            LOGGING.info('Extracting followers for all target users in project "%s"' % project.name)
            project.extract_followers_from_all_target_users(logger=LOGGING)

