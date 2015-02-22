# -*- coding: utf-8 -*-
from Queue import Full

from optparse import make_option
import time
import psutil
from core.models import TwitterBot
from core.scrapper.utils import get_2_args
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

            if bot:
                settings.TAKE_SCREENSHOTS = True

            num_threads, max_lookups = get_2_args(args)

            TwitterBot.objects.perform_sending_tweets(bot=bot, num_threads=num_threads, max_lookups=max_lookups)

            time.sleep(settings.TIME_SLEEPING_FOR_RESPAWN_TWEET_SENDER)
        except Full as e:
            settings.LOGGER.warning('Timeout exceeded, full threadpool queue')
            raise FatalError(e)
        except ProjectRunningWithoutBots:
            pass
        except Exception as e:
            raise FatalError(e)
        finally:
            # quitamos todos los phantomjs que hayan quedado ejecutándose
            phantomjs_to_kill = 'phantomjs_prod' if settings.PROD_MODE else 'phantomjs_dev'
            settings.LOGGER.debug('Killing all %s running processes..' % phantomjs_to_kill)
            for proc in psutil.process_iter():
                if phantomjs_to_kill in proc.name():
                    proc.kill()

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)

