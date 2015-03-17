from project.models import Extractor, Tweet
from project.exceptions import FatalError, NoRunningProjects, NoAvaiableExtractors
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand


MODULE_NAME = __name__.split('.')[-1]


class Command(BaseCommand):
    help = 'Process tweet for tweet sender given a pending to send tweet pk'

    def handle(self, *args, **options):
        set_logger(__name__)

        settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)

        try:
            mention_pk = int(args[0]) if args else None
            if mention_pk:
                Tweet.objects.process_mention(mention_pk)
                print 'Mention %i processed ok' % mention_pk
            else:
                raise Exception('Tweet pk needed!')
        except Exception as e:
            raise FatalError(e)

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)