# -*- coding: utf-8 -*-
from django.db.models import Count, Q, Max, Manager
from django.db.models.query import QuerySet
import os
import time

from django.db import models, connection
from core.querysets import TwitterBotQuerySet, ProxyQuerySet
from scrapper.thread_pool import ThreadPool
from scrapper.utils import utc_now
from twitter_bots import settings
from threading import Lock
mutex = Lock()


# https://djangosnippets.org/snippets/562/
# https://gist.github.com/allanlei/1090982
# class CustomManager(Manager):
    # def __init__(self, qs_class=models.query.QuerySet):
    #     super(CustomManager,self).__init__()
    #     self.queryset_class = qs_class
    #
    # def get_query_set(self):
    #     return self.queryset_class(self.model)
    #
    # def __getattr__(self, attr, *args):
    #     try:
    #         return getattr(self.__class__, attr, *args)
    #     except AttributeError:
    #         return getattr(self.get_query_set(), attr, *args)

class MyManager(Manager):
    def raw_as_qs(self, raw_query, params=()):
        """Execute a raw query and return a QuerySet.  The first column in the
        result set must be the id field for the model.
        :type raw_query: str | unicode
        :type params: tuple[T] | dict[str | unicode, T]
        :rtype: django.db.models.query.QuerySet
        """
        cursor = connection.cursor()
        try:
            cursor.execute(raw_query, params)
            return self.filter(id__in=(x[0] for x in cursor))
        finally:
            cursor.close()


# para cosas de multiproceso, donde había que llamar al método fuera de la clase
# def unwrap_self_send_tweet(*args):
#     from models import TwitterBot
#     return TwitterBot.objects.send_tweet(*args)

# def f(task_num, lock):
#     print task_num


class TwitterBotManager(models.Manager):
    def create_bot(self, **kwargs):
        try:
            connection.close()
            mutex.acquire()
            bot = self.create(**kwargs)
            bot.populate()
        finally:
            mutex.release()

        bot.complete_creation()

    def create_bots(self, num_bots=None):
        self.clean_unregistered()
        self.put_previous_being_created_to_false()

        from core.models import Proxy
        proxies = Proxy.objects.available_for_registration()

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

    def clean_unregistered(self):
        unregistered = self.unregistered()
        if unregistered.exists():
            settings.LOGGER.warning('Found %s unregistered bots and will be deleted' % unregistered.count())
            unregistered.delete()

    def put_previous_being_created_to_false(self):
        self.filter(is_being_created=True).update(is_being_created=False)

    def send_tweet_from_pending_queue(self):
        """Escoge un tweet pendiente de enviar cuyo robot no esté enviando actualmente"""
        from project.models import Tweet
        try:
            connection.close()
            tweet_to_send = None
            try:
                mutex.acquire()

                tweet_to_send = Tweet.objects.get_tweet_ready_to_send()
                tweet_to_send.sending = True
                tweet_to_send.save()
            finally:
                mutex.release()

            if tweet_to_send:
                tweet_to_send.send()
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

    def finish_creations(self):
        """Mira qué robots aparecen incompletos y termina de hacer en cada uno lo que quede"""
        uncompleted_bots = self.uncompleted()
        if uncompleted_bots.exists():
            pool = ThreadPool(settings.MAX_THREADS_COMPLETING_PENDANT_BOTS)
            for bot in uncompleted_bots.all():
                pool.add_task(bot.complete_creation)
            pool.wait_completion()
        else:
            settings.LOGGER.info('There is no more pendant bots to complete')
            time.sleep(60)

    #
    # Proxy methods to queryset
    #

    def get_queryset(self):
        return TwitterBotQuerySet(self.model, using=self._db)

    def unregistered(self):
        return self.get_queryset().unregistered()

    def usable(self):
        return self.get_queryset().usable()

    def registrable(self):
        return self.get_queryset().registrable()

    def with_valid_proxy_for_registration(self):
        return self.get_queryset().with_valid_proxy_for_registration()

    def with_valid_proxy_for_usage(self):
        return self.get_queryset().with_valid_proxy_for_usage()

    def uncompleted(self):
        return self.get_queryset().uncompleted()

    def completed(self):
        return self.get_queryset().completed()

    def twitteable(self):
        return self.get_queryset().twitteable()

    def without_tweet_to_send_queue_full(self):
        return self.get_queryset().without_tweet_to_send_queue_full()

    def total_from_proxies_group(self, proxies_group):
        return self.get_queryset().total_from_proxies_group(proxies_group)

    def registered_by_proxies_group(self, proxies_group):
        return self.get_queryset().registered_by_proxies_group(proxies_group)

    def using_proxies_group(self, proxies_group):
        return self.get_queryset().using_proxies_group(proxies_group)

    def using_in_project(self, project):
        return self.get_queryset().using_in_project(project)

    def using_in_running_projects(self):
        return self.get_queryset().using_in_running_projects()


class ProxyManager(MyManager):
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
                    settings.LOGGER.warning('file %s has not proxies inside' % os.path.join(dirpath, filename))
                    # raise Exception('file %s has not proxies inside' % os.path.join(dirpath, filename))
        return txt_proxies

    def sync_proxies(self):
        "Sincroniza BD y los proxies disponibles en los txt"

        def check_not_in_proxies_txts():
            """En BD se desmarca aquellos proxies que ya no estén en los .txt, ya que cada mes
            se renuevan los .txt con los nuevos"""

            def is_on_txt(db_proxy):
                for txt_proxy, txt_proxy_provider in txt_proxies:
                    if txt_proxy == db_proxy.proxy:
                        return True
                return False

            settings.LOGGER.info('Checking proxies in txts..')
            not_in_txts_proxies_count = 0  # cuenta el número de proxies que no aparecen en los txts
            db_proxies = self.all()
            for db_proxy in db_proxies:
                if is_on_txt(db_proxy):
                    db_proxy.is_in_proxies_txts = True
                    db_proxy.date_not_in_proxies_txts = None
                    db_proxy.save()
                elif db_proxy.is_in_proxies_txts:
                    # si no está en los txt y estaba marcado como que estaba lo cambiamos
                    db_proxy.is_in_proxies_txts = False
                    db_proxy.date_not_in_proxies_txts = utc_now()
                    db_proxy.save()
                    not_in_txts_proxies_count += 1
                    settings.LOGGER.info('Proxy %s @ %s marked as not appeared in proxies txts' % (db_proxy.proxy, db_proxy.proxy_provider))

            settings.LOGGER.info('%i proxies marked as not appeared in proxies txts' % not_in_txts_proxies_count)

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
        check_not_in_proxies_txts()
        add_new_proxies()

    def get_proxy_providers(self):
        "Devuelve la lista "

    #
    # PROXY QUERYSET
    #

    def get_queryset(self):
        return ProxyQuerySet(self.model, using=self._db)

    def available_for_usage(self):
        return self.get_queryset().available_for_usage()

    def available_for_registration(self):
        return self.get_queryset().available_for_registration()

    def without_any_dead_bot(self):
        return self.get_queryset().without_any_dead_bot()

    def with_at_least_one_dead_bot(self):
        return self.get_queryset().with_at_least_one_dead_bot()

    def using_in_running_projects(self):
        return self.get_queryset().using_in_running_projects()


