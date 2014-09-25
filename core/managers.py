# -*- coding: utf-8 -*-
import os
import random
import datetime
import time

from django.db import models
from scrapper.exceptions import BotDetectedAsSpammerException
from scrapper.thread_pool import ThreadPool
from twitter_bots import settings
from twitter_bots.settings import LOGGER
from multiprocessing import Lock
mutex = Lock()


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

    def get_bot_available_to_tweet(self, tweet):
        bots = self.get_all_bots().filter(it_works=True)
        for bot in bots:
            if bot.can_tweet(tweet):
                return bot

    def get_all_bots(self):
        "Escoge todos aquellos bots que tengan phantomJS"
        return self.filter(webdriver='PH').exclude(proxy='tor').exclude(must_verify_phone=True)

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

    def send_tweet(self, ignore_exceptions=False):
        from project.models import Tweet
        tweet = bot = None
        try:
            # PONEMOS CANDADO
            mutex.acquire()

            tweet = Tweet.objects.get_pending()[0]
            tweet_msg = tweet.compose()
            bot = self.get_bot_available_to_tweet(tweet)
            if bot:
                tweet.sending = True
                tweet.bot_used = bot
                tweet.save()
                LOGGER.info('Bot %s sending tweet: "%s"' % (bot.username, tweet_msg))

                # QUITAMOS CANDADO
                mutex.release()

                bot.scrapper.screenshots_dir = str(tweet.pk)
                bot.scrapper.open_browser()
                bot.scrapper.go_to(settings.URLS['twitter_login'])
                bot.scrapper.send_tweet(tweet_msg)
                tweet.sending = False
                tweet.sent_ok = True
                tweet.date_sent = datetime.datetime.now()
                tweet.save()
                bot.scrapper.close_browser()
                LOGGER.info('Bot %s sent tweet ok: "%s"' % (bot.username, tweet_msg))
            else:
                raise Exception('No more bots available for sending pending tweets')
        except Exception as ex:
            LOGGER.exception('')
            try:
                LOGGER.exception('Error sending tweet:\n "%s" \nby bot %s' % (tweet_msg, bot.username))
                tweet.sending = False
                tweet.bot = None
                tweet.save()
                bot.scrapper.close_browser()
            except Exception as ex:
                LOGGER.exception('')
                if ignore_exceptions:
                    LOGGER.info('ignoring exception..')
                else:
                    raise ex

            if ignore_exceptions:
                LOGGER.info('ignoring exception..')
            else:
                raise ex

    def send_pending_tweets(self):
        from project.models import Tweet
        Tweet.objects.clean_pending()
        pending_tweets = Tweet.objects.get_pending()
        LOGGER.info('--- Sending %s pending tweets ---' % pending_tweets.count())
        pool = ThreadPool(settings.MAX_THREADS)
        # for _ in pending_tweets:
        while True:
            pool.add_task(self.send_tweet, ignore_exceptions=True)
            if Tweet.objects.all_sent_ok():
                break
            else:
                time.sleep(0.3)
        pool.wait_completion()
        LOGGER.info('Tweets sent ok')

    def process_all_bots(self):
        bots = self.get_all_bots()
        LOGGER.info('Processing %i bots..' % bots.count())
        pool = ThreadPool(settings.MAX_THREADS)
        for bot in bots:
            pool.add_task(bot.process, ignore_exceptions=True)
        pool.wait_completion()
        LOGGER.info('%i bots processed ok' % bots.count())


