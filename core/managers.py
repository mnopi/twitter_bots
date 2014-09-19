# -*- coding: utf-8 -*-
import os

from django.db import models
from scrapper.exceptions import BotDetectedAsSpammerException
from scrapper.thread_pool import ThreadPool
from twitter_bots import settings
from twitter_bots.settings import LOGGER


class TwitterBotManager(models.Manager):
    def create_bot(self, **kwargs):
        ignore_exceptions = kwargs['ignore_exceptions'] if 'ignore_exceptions' in kwargs else False
        if 'ignore_exceptions' in kwargs:
            kwargs.pop('ignore_exceptions')
        bot = self.create(**kwargs)
        return bot.process(ignore_exceptions=ignore_exceptions)

    def create_bots(self, num_bots, **kwargs):
        pool = ThreadPool(settings.MAX_THREADS)
        for _ in range(0, num_bots):
            pool.add_task(self.create_bot, ignore_exceptions=True)
        pool.wait_completion()

    def check_listed_proxy(self, proxy):
        """Mira si el proxy está en las listas de proxies actuales, por si el usuario no se usó hace
        mucho tiempo y se refrescó la lista de proxies con los proveedores, ya que lo hacen cada mes normalmente"""
        if not settings.TOR_MODE:
            found_listed_proxy = False
            proxies_folder = os.path.join(settings.PROJECT_ROOT, 'core', 'proxies')
            for (dirpath, dirnames, filenames) in os.walk(proxies_folder):
                if found_listed_proxy: break
                for filename in filenames:  # myprivateproxy.txt
                    if found_listed_proxy: break
                    with open(os.path.join(dirpath, filename)) as f:
                        proxies_lines = f.readlines()
                        for pl in proxies_lines:
                            pl = pl.replace('\n', '')
                            pl = pl.replace(' ', '')
                            if pl == proxy:
                                found_listed_proxy = True
                                break

            if not found_listed_proxy:
                LOGGER.info('Proxy %s not listed' % proxy)

            return found_listed_proxy
        else:
            # si estamos en modo TOR siempre vamos a decir que el proxy está en listas
            return True

    def get_valid_bot(self, **kwargs):
        "De todo el conjunto de bots, escoge el primer bot considerado válido"
        kwargs.update(it_works=True)
        bot = self.get_all_bots(**kwargs)[0]
        try:
            bot.scrapper.login()
            return bot
        except Exception:
            bot.mark_as_not_twitter_registered_ok()
            self.get_valid_bot(**kwargs)

    def get_all_bots(self, **kwargs):
        "Escoge todos aquellos bots que tengan phantomJS y con los filtros dados por kwargs"
        kwargs.update(webdriver='PH')
        return self.filter(**kwargs).exclude(proxy='tor', must_verify_phone=True)

    def send_mention(self, username, tweet_msg):
        "Del conjunto de robots se escoge uno para enviar el tweet al usuario"
        bot = self.get_valid_bot()
        bot.scrapper.send_mention(username, tweet_msg)

    def send_mentions(self, user_list, tweet_msg):
        "Se escoje un robot para mandar el tweet_msg a todos los usuarios de user_list"
        bot = self.get_valid_bot()
        try:
            for username in user_list:
                bot.scrapper.send_mention(username, tweet_msg)
        except BotDetectedAsSpammerException:
            self.send_mentions(user_list, tweet_msg)

    def process_all_bots(self):
        bots = self.get_all_bots()
        LOGGER.info('Processing %i bots..' % bots.count())
        pool = ThreadPool(settings.MAX_THREADS)
        for bot in bots:
            pool.add_task(bot.process, ignore_exceptions=True)
        pool.wait_completion()
        LOGGER.info('%i bots processed ok' % bots.count())


