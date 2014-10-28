# -*- coding: utf-8 -*-
import multiprocessing
import random
from django.db.models import Count, Q, Max
import os
import time
import threading
import datetime

from django.db import models, connection
import pytz
from project.exceptions import TwitteableBotsNotFound
from scrapper.exceptions import BotDetectedAsSpammerException, NoMoreAvaiableProxiesForCreatingBots
from scrapper.thread_pool import ThreadPool
from twitter_bots import settings
from threading import Lock
mutex = Lock()

# def unwrap_self_send_tweet(*args):
#     from models import TwitterBot
#     return TwitterBot.objects.send_tweet(*args)

# def f(task_num, lock):
#     print task_num

class TwitterBotManager(models.Manager):
    def  create_bot(self, **kwargs):
        try:
            connection.close()
            mutex.acquire()
            bot = self.create(**kwargs)
            bot.populate()
        finally:
            mutex.release()

        bot.complete_creation()

    def create_bots(self, num_bots=None):
        self.clean_unregistered_bots()
        self.put_previous_being_created_to_false()

        from core.models import Proxy
        proxies = Proxy.objects.get_available_proxies_for_registration()

        settings.LOGGER.info('Found %i avaiable proxies to create bots at this moment' % len(proxies))

        pool = ThreadPool(settings.MAX_THREADS_CREATING_BOTS)
        num_bots = num_bots or len(proxies)
        for task_num in range(num_bots):
            settings.LOGGER.info('Adding task %i' % task_num)
            pool.add_task(self.create_bot)
        pool.wait_completion()

        # threads = []
        # for n in range(num_bots):
        #     thread = threading.Thread(target=self.create_bot)
        #     thread.start()
        #     threads.append(thread)
        # # to wait until all three functions are finished
        # for thread in threads:
        #     thread.join()

    def clean_unregistered_bots(self):
        unregistered = self.get_unregistered_bots()
        if unregistered.exists():
            settings.LOGGER.warning('Found %s unregistered bots and will be deleted' % unregistered.count())
            unregistered.delete()

    def put_previous_being_created_to_false(self):
        self.filter(is_being_created=True).update(is_being_created=False)

    def get_unregistered_bots(self):
        return self.filter(email_registered_ok=False, twitter_registered_ok=False)

    def get_uncompleted_bots(self):
        """Devuelve todos los robots pendientes de terminar registros, perfil, etc"""
        return self.get_all_active_bots(take_suspended=True).filter(
            Q(twitter_registered_ok=False) |
            Q(twitter_confirmed_email_ok=False) |
            Q(twitter_avatar_completed=False) |
            Q(twitter_bio_completed=False) |
            Q(is_suspended=True)
        ).order_by('-date')

    def get_one_bot_with_tweet_to_send(self):
        """
        devuelve la tupla (bot, tweet) que el primer bot pueda tuitear. En caso de no poderse
        construir el tweet con ningún bot entonces se lanza excepción
        """
        for bot in self.get_all_twitteable_bots().all():
            tweet_to_send = bot.make_mention_tweet_to_send()
            if tweet_to_send:
                return bot, tweet_to_send

        raise TwitteableBotsNotFound()

    def get_all_active_bots(self, take_suspended=False):
        """Escoge todos los bots que se puedan usar, incluyendo completos e incompletos,
        pero que al menos tengan el correo registrado, con proxy ok y que no estén siendo creados"""
        bots = self.filter(
                webdriver='PH',
                is_suspended_email=False,
                email_registered_ok=True,
            )\
            .exclude(proxy__proxy='tor')\
            .exclude(proxy__is_unavailable_for_registration=True)\
            .exclude(proxy__is_unavailable_for_use=True)\
            .exclude(proxy__is_phone_required=True)\
            .exclude(is_being_created=True)

        if not take_suspended:
            bots = bots.filter(is_suspended=False)

        return bots

    def get_completed_bots(self):
        """De los bots que toma devuelve sólo aquellos que estén completamente creados"""
        return self.get_all_active_bots()\
            .filter(
                twitter_confirmed_email_ok=True,
                twitter_avatar_completed=True,
                twitter_bio_completed=True,
            )

    def get_all_twitteable_bots(self):
        """
        Entre los completamente creados coge los que no sean extractores, para evitar que twitter detecte
        actividad múltiple desde misma cuenta
        """
        return self.get_completed_bots().filter(extractor=None)

    def send_tweet_from_pending_queue(self):
        """Escoge un tweet pendiente de enviar cuyo robot no esté enviando actualmente"""
        # mutex.acquire()
        # print '%s executing' % get_thread_name()
        # mutex.release()
        # raise Exception()
        from project.models import Tweet
        try:
            connection.close()
            try:
                mutex.acquire()

                tweet = Tweet.objects.get_tweet_ready_to_send()
                tweet.sending = True
                tweet.save()
            finally:
                mutex.release()

            tweet.send()
        except Exception as e:
            raise e

    def send_pending_tweets(self):
        pool = ThreadPool(settings.MAX_THREADS_SENDING_TWEETS)

        for task_num in range(settings.TOTAL_TASKS_SENDING_TWEETS):
            pool.add_task(self.send_tweet_from_pending_queue)
        pool.wait_completion()

        # manager = multiprocessing.Manager()
        # lock = manager.Lock()
        # pool = multiprocessing.Pool(processes=settings.MAX_THREADS_SENDING_TWEETS)
        # for i in xrange(settings.TASKS_PER_EXECUTION):
        #     pool.apply_async(func=unwrap_self_send_tweet, args=(i,lock))
        # pool.close()
        # pool.join()

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

    def complete_pendant_bot_creations(self):
        """Mira qué robots aparecen incompletos y termina de hacer en cada uno lo que quede"""
        uncompleted_bots = self.get_uncompleted_bots()
        if uncompleted_bots.exists():
            pool = ThreadPool(settings.MAX_THREADS_COMPLETING_PENDANT_BOTS)
            for bot in uncompleted_bots.all():
                pool.add_task(bot.complete_creation)
            pool.wait_completion()
        else:
            settings.LOGGER.info('There is no more pendant bots to complete')
            time.sleep(60)


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

    def get_valid_proxies(self):
        """Devuelve los proxies válidos para poder crear nuevos bots"""
        return self.filter(
            is_unavailable_for_registration=False,
            is_unavailable_for_use=False,
            is_phone_required=False,
        )

    def get_available_proxies_for_login(self):
        """
        Para devolver proxies disponibles para iniciar sesión con bot y tuitear etc:
            - proxies que tengan menos de x bots asignados para logueo
            -
        """
        pass

    def get_available_proxies_for_registration(self):
        """Devuelve proxies disponibles para registrar un bot"""

        # proxies válidos que tengan un número de bots inferior al límite y con ningún bot suspendido
        proxies_with_available_space = self.get_valid_proxies()\
            .annotate(num_bots=Count('twitter_bots'))\
            .filter(num_bots__lt=settings.MAX_TWT_BOTS_PER_PROXY_FOR_REGISTRATIONS)

        ids = []

        # proxies sin bots
        ids.extend([
            result['id'] for result in proxies_with_available_space.filter(twitter_bots=None).values('id')
        ])

        # proxies con bots, aquellos que:
        #   - bot más reciente sea igual o más antiguo que la fecha de registro más antigua permitida
        #   - no tengan ni un bot como suspendido
        oldest_allowed_registation_date = datetime.datetime.now().replace(tzinfo=pytz.utc) - \
                                       datetime.timedelta(days=settings.MIN_DAYS_BETWEEN_REGISTRATIONS_PER_PROXY)
        ids.extend([
            result['id'] for result in
                proxies_with_available_space\
                .annotate(latest_bot_date=Max('twitter_bots__date'))\
                .filter(latest_bot_date__lte=oldest_allowed_registation_date)\
                .filter(twitter_bots__is_suspended=False)\
                .values('id')
        ])

        available_proxies = self.filter(id__in=ids)

        if not available_proxies:
            raise NoMoreAvaiableProxiesForCreatingBots()

        return available_proxies
