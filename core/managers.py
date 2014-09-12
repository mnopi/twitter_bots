# -*- coding: utf-8 -*-
import os

from django.db import models
from scrapper.exceptions import BotDetectedAsSpammerException
from scrapper.thread_pool import ThreadPool
from twitter_bots import settings
from twitter_bots.settings import LOGGER


class TwitterBotManager(models.Manager):
    def register_bot(self, bot):
        bot.populate()
        if not bot.proxy:
            bot.assign_proxy()
        bot.perform_registrations()
        return bot

    def create_bot(self, **kwargs):
        bot = self.create(**kwargs)
        self.register_bot(bot)

    def create_bots(self, num_bots, **kwargs):
        pool = ThreadPool(settings.MAX_THREADS)
        bots = []
        for _ in range(0, num_bots):
            bot = self.create(**kwargs)
            pool.add_task(self.register_bot, bot)
            bots.append(bot)
        pool.wait_completion()
        return bots

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
                LOGGER.info('Proxy %s @ %s not listed' % (self.proxy, self.proxy_provider))

            return found_listed_proxy
        else:
            # si estamos en modo TOR siempre vamos a decir que el proxy está en listas
            return True

    def get_valid_bot(self, from_kamikaze=None):
        bots = self.filter(it_works=True)
        if from_kamikaze:
            bots = bots.filter(is_kamikaze=from_kamikaze)
        bot = bots[0]
        try:
            bot.scrapper.login()
            return bot
        except Exception:
            bot.mark_as_not_twitter_registered_ok()
            self.get_valid_bot(from_kamikaze=from_kamikaze)

    def send_mention(self, username, tweet_msg, from_kamikaze=None):
        "Del conjunto de robots se escoge uno para enviar el tweet al usuario"
        bot = self.get_valid_bot(from_kamikaze=from_kamikaze)
        bot.scrapper.send_mention(username, tweet_msg)

    def send_mentions(self, user_list, tweet_msg, from_kamikaze=None):
        "Se escoje un robot para mandar el tweet_msg a todos los usuarios de user_list"
        bot = self.get_valid_bot(from_kamikaze=from_kamikaze)
        try:
            for username in user_list:
                bot.scrapper.send_mention(username, tweet_msg)
        except BotDetectedAsSpammerException:
            self.send_mentions(user_list, tweet_msg, from_kamikaze=from_kamikaze)