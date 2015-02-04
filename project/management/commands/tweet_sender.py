# -*- coding: utf-8 -*-
from Queue import Full

from optparse import make_option
import time
from core.models import TwitterBot
from core.scrapper.utils import get_th_tasks
from project.models import Tweet, Project
from project.exceptions import FatalError, ProjectRunningWithoutBots
from twitter_bots import settings
from django.core.management.base import BaseCommand
from twitter_bots.settings import set_logger


MODULE_NAME = __name__.split('.')[-1]


class Command(BaseCommand):
    help = 'Send pending tweets'

    option_list = BaseCommand.option_list + (
        make_option('--bot',
            dest='bot',
            help='Send pending tweets only from given bot'),
        )

    def handle(self, *args, **options):
        set_logger(__name__)
        settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)

        try:
            Tweet.objects.clean_not_ok()
            TwitterBot.objects.filter(is_following=True).update(is_following=False)
            Project.objects.check_bots_on_all_running()

            bot = TwitterBot.objects.get(username=options['bot']) \
                if 'bot' in options and options['bot'] \
                else None

            num_threads, num_tasks = get_th_tasks(args)

            TwitterBot.objects.send_mentions_from_queue(bot=bot, num_threads=num_threads, num_tasks=num_tasks)

            time.sleep(settings.TIME_SLEEPING_FOR_RESPAWN_TWEET_SENDER)
        except Full as e:
            settings.LOGGER.warning('Timeout exceeded, full threadpool queue')
            raise FatalError(e)
        except ProjectRunningWithoutBots:
            pass
        except Exception as e:
            raise FatalError(e)

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)

