# -*- coding: utf-8 -*-
from optparse import make_option

from django.core.management.base import BaseCommand
from core.models import TwitterBot
from scrapper.thread_pool import ThreadPool
from scrapper import settings
from twitter_bots.settings import LOGGER


class Command(BaseCommand):
    help = u'Comprueba si los usuarios que todavía están marcados como "it_works" siguen activos'

    option_list = BaseCommand.option_list + (
        make_option('--webdriver',
            action='store',
            dest='webdriver',
            default='fi',
            help='choose webdriver to use: \n\t--webdriver=fi (firefox)\n\t--webdriver=ph (phantomjs)'),
        )

    def handle(self, *args, **options):
        settings.WEBDRIVER = options['webdriver'].upper()
        num_bots = int(args[0])

        def create_bot(bot):
            bot.process()
            LOGGER.info('bot %s created' % bot.username)

        pool = ThreadPool(settings.MAX_THREADS)

        bots = TwitterBot.objects.create_bots(num_bots)
        for bot in bots:
            pool.add_task(create_bot, bot)

        pool.wait_completion()


        # for i in range(0, num_bots):
        #     t = threading.Thread(target=create_bot, args=(i,))
        #     t.start()


