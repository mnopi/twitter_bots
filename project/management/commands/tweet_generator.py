import time
from project.models import Project, TwitterUser
from twitter_bots import settings
from twitter_bots.settings import set_logger

from django.core.management.base import BaseCommand, CommandError

set_logger('tweet_generator')


class Command(BaseCommand):
    help = 'Creates bots'

    def handle(self, *args, **options):
        settings.LOGGER.info('-- INITIALIZED TWEET CREATOR --')
        for project in Project.objects.all():
            project.create_tweets(platform=TwitterUser.ANDROID)
        settings.LOGGER.info('-- FINISHED TWEET CREATOR --')
        time.sleep(15)

