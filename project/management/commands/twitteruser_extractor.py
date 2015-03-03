from project.models import Extractor
from project.exceptions import FatalError, NoRunningProjects, NoAvaiableExtractors
from twitter_bots import settings
from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand


MODULE_NAME = __name__.split('.')[-1]


class Command(BaseCommand):
    help = 'Extract followers from all target users'

    def handle(self, *args, **options):
        set_logger(__name__)

        settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)

        try:
            Extractor.objects.extract_twitterusers_for_running_projects()
            # threads = []
            # if settings.EXTRACT_FOLLOWERS:
            #     threads.append(threading.Thread(target=Extractor.objects.extract_twitterusers_for_running_projects))
            # # if settings.EXTRACT_HASHTAGS:
            #     # threads.append(threading.Thread(target=Extractor.objects.extract_hashtags))
            # for th in threads:
            #     th.start()
            #
            # # to wait until all threads are finished
            # for th in threads:
            #     th.join()
        except (NoAvaiableExtractors,
                NoRunningProjects):
            pass
        except Exception as e:
            raise FatalError(e)

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)