# -*- coding: utf-8 -*-

from optparse import make_option
import time
from core.models import TwitterBot
from project.models import Tweet, TweetCheckingMention
from project.exceptions import FatalError
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

        def clean():
            """hacemos esto para que no salgan los robots como ocupados (enviando tweet, comprobando mención..)"""

            Tweet.objects.put_sending_to_not_sending()
            TweetCheckingMention.objects.put_checking_to_not_checking()
            Tweet.objects.remove_wrong_constructed()

        set_logger(__name__)
        settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)

        try:
            clean()

            bot = TwitterBot.objects.get(username=options['bot']) \
                if 'bot' in options and options['bot'] \
                else None

            num_threads = int(args[0]) if args else None

            TwitterBot.objects.send_mentions_from_queue(bot=bot, num_threads=num_threads)

            time.sleep(settings.TIME_SLEEPING_FOR_RESPAWN_TWEET_SENDER)
        except Exception as e:
            raise FatalError(e)

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)

