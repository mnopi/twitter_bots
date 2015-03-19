from core.scrapper.exceptions import PageLoadError, FailureSendingTweet
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

        # settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)

        mention_pk = int(args[0]) if args else None
        try:
            burst_size = int(args[1]) if args else None
        except IndexError:
            burst_size = None

        try:
            if mention_pk:
                output = Tweet.objects.process_mention(mention_pk, burst_size=burst_size)
                print output
            else:
                raise Exception('Tweet pk needed!')
        except Tweet.DoesNotExist:
            print 'Mention %i does not exists!' % mention_pk
        # except PageLoadError:
        #     print 'Pageload error. Maybe u need to add this host public ip address to authorized ones on proxy provider'
        except Exception as e:
            raise FatalError(e)

        # settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)