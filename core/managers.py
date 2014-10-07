# -*- coding: utf-8 -*-
import random
import os
import time
import threading
import datetime

from django.db import models
import pytz
from project.exceptions import BotsWithTweetNotFoundException
from scrapper.exceptions import BotDetectedAsSpammerException, NoMoreAvaiableProxiesException
from scrapper.thread_pool import ThreadPool
from twitter_bots import settings
from multiprocessing import Lock
mutex = Lock()


class TwitterBotManager(models.Manager):
    def create_bot(self, **kwargs):
        try:
            mutex.acquire()
            bot = self.create(**kwargs)
            bot.populate()
        finally:
            mutex.release()

        bot.register_accounts()

    def create_bots(self):
        try:
            proxies = self.get_available_proxies()
            if len(proxies) < settings.MAX_THREADS_CREATING_BOTS:
                num_bots = len(proxies)
            else:
                num_bots = settings.MAX_THREADS_CREATING_BOTS

            threads = []
            for n in range(num_bots):
                thread = threading.Thread(target=self.create_bot)
                thread.start()
                threads.append(thread)
            # to wait until all three functions are finished
            for thread in threads:
                thread.join()

            # pool = ThreadPool(settings.MAX_THREADS)
            # for _ in range(0, num_bots):
            #     pool.add_task(self.create_bot, ignore_exceptions=True)
            # pool.wait_completion()
        except NoMoreAvaiableProxiesException:
            time.sleep(120)

    def clean_unregistered_bots(self):
        unregistered = self.get_unregistered_bots()
        if unregistered.exists():
            settings.LOGGER.warning('Found %s unregistered bots and will be deleted' % unregistered.count())
            unregistered.delete()

    def get_unregistered_bots(self):
        return self.filter(email_registered_ok=False, twitter_registered_ok=False).exclude(must_verify_phone=True)

    def get_available_proxies(self):
        """Busca los proxies disponibles"""

        def check_avaiable_proxy(proxy):
            """
            Para que un proxy esté disponible para el bot se tiene que cumplir:
                -   que no haya que verificar teléfono
                -   que el número de bots con ese proxy no superen el máximo por proxy (space_ok)
                -   que el último usuario que se registró usando ese proxy lo haya hecho
                    hace más de el periodo mínimo de días (diff_ok)
            """
            if proxy:
                num_users_with_that_proxy = self.filter(proxy=proxy).count()
                proxy_under_phone_verification = self.filter(proxy=proxy, must_verify_phone=True)
                space_ok = not proxy_under_phone_verification and \
                           num_users_with_that_proxy <= settings.MAX_TWT_BOTS_PER_PROXY
                if space_ok:
                    if num_users_with_that_proxy > 0:
                        latest_user_with_that_proxy = self.filter(proxy=proxy).latest('date')
                        diff_ok = (datetime.datetime.now().replace(tzinfo=pytz.utc)
                                   - latest_user_with_that_proxy.date).days >= settings.MIN_DAYS_BETWEEN_REGISTRATIONS_PER_PROXY
                        return diff_ok
                    else:
                        # proxy libre
                        return True
                else:
                    return False
            else:
                # si 'proxy' es una cadena vacía..
                return False

        settings.LOGGER.info('Trying to get available proxies')
        available_proxies = []
        for (dirpath, dirnames, filenames) in os.walk(settings.PROXIES_DIR):
            for filename in filenames:  # myprivateproxy.txt
                with open(os.path.join(dirpath, filename)) as f:
                    proxies_lines = f.readlines()
                    for proxy in proxies_lines:
                        proxy = proxy.replace('\n', '')
                        proxy = proxy.replace(' ', '')
                        if check_avaiable_proxy(proxy):
                            proxy_provider = filename.split('.')[0]
                            available_proxies.append((proxy, proxy_provider))

        if available_proxies:
            settings.LOGGER.info('%i available proxies detected' % len(available_proxies))
            return available_proxies
        else:
            raise NoMoreAvaiableProxiesException()

    def check_listed_proxy(self, proxy):
        """Mira si el proxy está en las listas de proxies actuales, por si el usuario no se usó hace
        mucho tiempo y se refrescó la lista de proxies con los proveedores, ya que lo hacen cada mes normalmente"""
        found_listed_proxy = False
        for (dirpath, dirnames, filenames) in os.walk(settings.PROXIES_DIR):
            if found_listed_proxy:
                break
            for filename in filenames:  # myprivateproxy.txt, squidproxies..
                if found_listed_proxy:
                    break
                with open(os.path.join(dirpath, filename)) as f:
                    proxies_lines = f.readlines()
                    for pl in proxies_lines:
                        pl = pl.replace('\n', '')
                        pl = pl.replace(' ', '')
                        if pl == proxy:
                            found_listed_proxy = True
                            break

        if not found_listed_proxy:
            settings.LOGGER.info('Proxy %s not listed' % proxy)

        return found_listed_proxy

    def get_bots_with_tweet_to_send(self, limit=None):
        """
        devuelve la tupla (bot, tweet) que el primer bot pueda tuitear. En caso de no poderse
        construir el tweet con ningún bot entonces se lanza excepción
        """
        avaiable_bots_with_tweet = []
        for bot in self.get_all_twitteable_bots():
            tweet_to_send = bot.make_tweet_to_send()
            if tweet_to_send:
                avaiable_bots_with_tweet.append((bot, tweet_to_send))
                settings.LOGGER.info('Added bot %s with tweet %s' % (bot.username, tweet_to_send.compose()))
                if limit and len(avaiable_bots_with_tweet) == limit:
                    break

        if len(avaiable_bots_with_tweet):
            settings.LOGGER.info('Found %i bots with tweet to send' % len(avaiable_bots_with_tweet))
            return avaiable_bots_with_tweet
        else:
            raise BotsWithTweetNotFoundException()

    def get_all_active_bots(self):
        """Escoge todos aquellos bots que tengan phantomJS, no tengan proxy tor y el proxy funcione"""
        return self.filter(webdriver='PH', is_active=True)\
            .exclude(proxy__proxy='tor')\
            .exclude(proxy__is_unavailable_for_use=True)

    def get_all_twitteable_bots(self):
        now_utc = datetime.datetime.now().replace(tzinfo=pytz.utc)
        random_seconds = random.randint(60*settings.TIME_BETWEEN_TWEETS[0], 60*settings.TIME_BETWEEN_TWEETS[1])  # entre 2 y 7 minutos por tweet
        date_sent_limit = now_utc - datetime.timedelta(seconds=random_seconds)

        return self.get_all_active_bots()\
            .exclude(tweets__sending=True)\
            .exclude(tweets__date_sent__gt=date_sent_limit)

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

    def send_tweet(self):
        """Escoge un robot cualquiera de los disponibles para enviar un tweet"""
        bots_with_tweet = self.get_bots_with_tweet_to_send(limit=1)
        bot, tweet = bots_with_tweet[0]
        bot.send_tweet(tweet)

    def send_tweets(self):
        # settings.LOGGER.info('--- Trying to send %i tweets ---' % settings.MAX_THREADS_SENDING_TWEETS)

        bots_with_tweet = self.get_bots_with_tweet_to_send()

        # threads = []
        # for bwt in bots_with_tweet:
        #     bot, tweet = bwt
        #     thread = threading.Thread(target=bot.send_tweet, args=tweet)
        #     thread.start()
        #     threads.append(thread)
        #
        # # to wait until all three functions are finished
        # for thread in threads:
        #     thread.join()

        pool = ThreadPool(settings.MAX_THREADS_SENDING_TWEETS)
        for bwt in bots_with_tweet:
            bot, tweet = bwt
            settings.LOGGER.info('Adding task (bot: %s, tweet: %s)' % (bot.username, tweet.compose()))
            pool.add_task(bot.send_tweet, tweet)
        pool.wait_completion()

    # def process_all_bots(self):
    #     bots = self.get_all_bots()
    #     settings.LOGGER.info('Processing %i bots..' % bots.count())
    #     pool = ThreadPool(settings.MAX_THREADS_CREATING_BOTS)
    #     for bot in bots:
    #         pool.add_task(bot.process, ignore_exceptions=True)
    #     pool.wait_completion()
    #     settings.LOGGER.info('%i bots processed ok' % bots.count())



class ProxyManager(models.Manager):
    def get_txt_proxies(self):
        """Devuelve una lista de todos los proxies metidos en los .txt"""
        txt_proxies = []
        for (dirpath, dirnames, filenames) in os.walk(settings.PROXIES_DIR):
            for filename in filenames:  # myprivateproxy.txt
                filename_has_proxies = False
                with open(os.path.join(dirpath, filename)) as f:
                    proxies_lines = f.readlines()
                    for proxy in proxies_lines:
                        proxy = proxy.replace('\n', '')
                        proxy = proxy.replace(' ', '')
                        proxy_provider = filename.split('.')[0]
                        txt_proxies.append((proxy, proxy_provider))
                        filename_has_proxies = True
                if not filename_has_proxies:
                    raise Exception('file %s has not proxies inside' % os.path.join(dirpath, filename))
        return txt_proxies

    def sync_proxies(self):
        "Sincroniza BD y los proxies disponibles en los txt"

        def clean_old_proxies():
            """Quita de BD aquellos proxies que ya no estén en los .txt, ya que cada mes
            se renuevan los .txt con los nuevos"""

            def is_on_txt(db_proxy):
                for txt_proxy, txt_proxy_provider in txt_proxies:
                    if txt_proxy == db_proxy.proxy:
                        return True
                return False

            settings.LOGGER.info('Cleaning old proxies..')
            old_count = 0
            db_proxies = self.all()
            for db_proxy in db_proxies:
                if not is_on_txt(db_proxy):
                    db_proxy.delete()
                    old_count += 1
                    settings.LOGGER.info('Deleted old proxy %s @ %s' % (db_proxy.proxy, db_proxy.proxy_provider))
            settings.LOGGER.info('%i old proxies removed ok from database' % old_count)

        def add_new_proxies():
            settings.LOGGER.info('Adding new proxies to database..')
            new_count = 0
            for txt_proxy, txt_proxy_provider in txt_proxies:
                if not self.filter(proxy=txt_proxy, proxy_provider=txt_proxy_provider).exists():
                    self.create(proxy=txt_proxy, proxy_provider=txt_proxy_provider)
                    settings.LOGGER.info('\tAdded new proxy %s @ %s' % (txt_proxy, txt_proxy_provider))
                    new_count += 1
            settings.LOGGER.info('%i new proxies added ok into database' % new_count)

        txt_proxies = self.get_txt_proxies()
        clean_old_proxies()
        add_new_proxies()
