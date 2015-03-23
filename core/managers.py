# -*- coding: utf-8 -*-
from multiprocessing import Pool
import dispy
from django.db.models import Count, Q, Max, Manager
from django.db.models.query import QuerySet
import os
import time

from django.db import models, connection, transaction
import multiprocessing
from core.querysets import TwitterBotQuerySet, ProxyQuerySet
from project.exceptions import *
from core.scrapper.thread_pool import ThreadPool
from core.scrapper.utils import utc_now
from twitter_bots import settings
from threading import Lock, BoundedSemaphore
mutex = Lock()

sem_mutweet_checking = BoundedSemaphore(value=3)


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
    def create_bots_from_files(self):
        """Crea bots a partir de los txt en core/bots"""

        def create_without_profile(bot):
            """Crea bot a partir de la línea leída"""

            settings.LOGGER.debug('Creating new bot %s..' % bot[0])

            # en caso de venir sin contraseña el email pondremos el mismo que para la cuenta de twitter
            try:
                email_password = bot[3]
            except IndexError:
                email_password = bot[1]

            bot_obj = self.create(
                username=bot[0].lower(),
                password_twitter=bot[1],
                email=bot[2],
                password_email=email_password,
                email_registered_ok=True,
                twitter_registered_ok=True,
                twitter_confirmed_email_ok=True,
                is_being_created=False
            )
            bot_obj.populate(from_bots_txts=True)
            return bot_obj

        def create_phone_verified(bot):
            """Creamos bot y añadimos que tiene avatar y teléfono"""

            bot_created = create_without_profile(bot)
            bot_created.is_phone_verified = True
            bot_created.phone_number = bot[-1]
            bot_created.real_name = ' '.join(bot[4:6])
            bot_created.twitter_avatar_completed = True
            bot_created.save()
            return bot_created

        def create_profiled(bot):
            bot_created = create_without_profile(bot)
            bot_created.twitter_avatar_completed = True
            bot_created.twitter_bio_completed = True
            bot_created.save()
            return bot_created

        def create_new_bots_from_file(file, fn_to_create):
            new_bots, existing_bots = [], []
            with open(file) as f:
                bots_lines = f.readlines()
                for bot in bots_lines:
                    bot = bot.replace('\n', '').replace(' ', '')
                    bot = bot.split(',') if ',' in bot else bot.split(':')
                    bot_username = bot[0].lower()
                    if not self.filter(username=bot_username).exists():
                        with transaction.atomic():
                            bot_created = fn_to_create(bot)
                        new_bots.append(bot_created)
                    else:
                        settings.LOGGER.debug('%s already exists on DB' % bot_username)
                        existing_bots.append(bot)
            return new_bots, existing_bots

        def extend_new_existant(l1, l2):
            """a l1 se extiende sus componentes 0 y 1 con los que tiene l2 en 0 y 1 respectivamente"""
            l1[0].extend(l2[0])
            l1[1].extend(l2[1])

        new_bots_dirs = {
            'non_profiled': os.path.join(settings.NEW_BOTS_DIR, 'non_profiled'),
            'profiled': os.path.join(settings.NEW_BOTS_DIR, 'profiled'),
            'phone_verified': os.path.join(settings.NEW_BOTS_DIR, 'phone_verified'),
        }

        non_profiled_bots = [], []
        profiled_bots = [], []
        phone_verified_bots = [], []

        for k, dir in new_bots_dirs.items():
            for (dirpath, dirnames, filenames) in os.walk(dir):
                settings.LOGGER.info('Checking bots files on %s dir..' % k)
                for filename in filenames:
                    settings.LOGGER.info('\tChecking file %s..' % filename)
                    path = os.path.join(dirpath, filename)
                    if k == 'non_profiled':
                        bots = create_new_bots_from_file(path, create_without_profile)
                        extend_new_existant(non_profiled_bots, bots)
                    elif k == 'profiled':
                        bots = create_new_bots_from_file(path, create_profiled)
                        extend_new_existant(profiled_bots, bots)
                    elif k == 'phone_verified':
                        bots = create_new_bots_from_file(path, create_phone_verified)
                        extend_new_existant(phone_verified_bots, bots)

        n1, n2, n3 = len(non_profiled_bots[0]), len(profiled_bots[0]), len(phone_verified_bots[0])
        ntotal = n1+n2+n3
        if ntotal:
            settings.LOGGER.info('New bots created: %i (%i without profile, %i profiled and %i phone verified)'
                                 %(ntotal, n1, n2, n3))
        else:
            settings.LOGGER.warning('No new bots created!. Ensure you added new bots files')

        e1, e2, e3 = len(non_profiled_bots[1]), len(profiled_bots[1]), len(phone_verified_bots[1])
        etotal = e1+e2+e3
        if etotal:
            settings.LOGGER.info('Existing bots: %i (%i without profile, %i profiled and %i phone verified)'
                                 %(etotal, e1, e2, e3))

    def create_bot(self, **kwargs):
        try:
            connection.close()
            mutex.acquire()
            bot = self.create(**kwargs)
            bot.populate()
        finally:
            mutex.release()

        bot.complete_creation(first_time=True)

    def create_bots(self, num_threads=None, num_tasks=None):
        from core.models import Proxy
        #self.clean_unregistered()
        self.put_previous_being_created_to_false()

        settings.LOGGER.info('Retrieving proxies available for registering bots..')
        proxies = Proxy.objects.available_to_assign_bots_for_registration()

        subnets_24_count = len(Proxy.objects.get_subnets_24(proxies))
        settings.LOGGER.info('There is %i available /24 subnets to create bots' % subnets_24_count)

        if proxies.exists():
            if num_threads == 1:
                self.create_bot()
            else:
                if num_tasks and num_tasks > subnets_24_count:
                    settings.LOGGER.warning('The num_tasks specified to create is higher than total /24 available subnets')
                    num_bots = subnets_24_count
                else:
                    num_bots = num_tasks or subnets_24_count

                pool = ThreadPool(num_threads or settings.MAX_THREADS_CREATING_BOTS)
                settings.LOGGER.info('Creating %d twitter bots..' % num_bots)
                for task_num in range(num_bots):
                    settings.LOGGER.info('Adding task %i' % task_num)
                    pool.add_task(self.create_bot)
                pool.wait_completion()
        else:
            raise NoMoreAvailableProxiesForRegistration()

        # threads = []
        # for n in range(num_bots):
        #     thread = threading.Thread(target=self.create_bot)
        #     thread.start()
        #     threads.append(thread)
        # # to wait until all three functions are finished
        # for thread in threads:
        #     thread.join()

    def clean_unregistered(self):
        unregistered = self.without_any_account_registered()
        if unregistered.exists():
            settings.LOGGER.warning('Found %s unregistered bots and will be deleted' % unregistered.count())
            unregistered.delete()

    def put_previous_being_created_to_false(self):
            self.filter(is_being_created=True).update(is_being_created=False)

    def queue_tasks_from_mention_queue(self, max_tweets=None, bot=None):
        """Consulta la cola de menciones para añadirlas a la cola de tareas"""
        from project.models import Tweet
        from project.management.commands.tweet_sender import do_process_mention
        import random
        from core.models import TwitterBot

        def pr():
            """Esto solo lo usamos para probar el threadpool"""
            settings.LOGGER.debug('starting..')
            time.sleep(random.randint(5,10))
            settings.LOGGER.debug('..done!')

        pending_mentions = Tweet.objects.get_queued_twitteruser_mentions_to_send(by_bot=bot)\
            .select_related('bot_used').select_related('bot_used__proxy_for_usage__proxies_group')
        if pending_mentions.exists():
            settings.LOGGER.info('Processing %d pending mentions (1 per available bot)..' % pending_mentions.count())

            # ponemos todas las menciones como enviando y a sus bots como usándose
            pending_mentions.update(sending=True)
            TwitterBot.objects.filter(pk__in=pending_mentions.values_list('bot_used__pk')).update(is_being_used=True)

            if max_tweets:
                pending_mentions = pending_mentions[:max_tweets]

            if max_tweets == 1 or bot:
                # pending_mentions[0].process_sending()
                do_process_mention(pending_mentions[0].pk) # todo:quitar esto, es para revisar si con celery se escribe bien tweet con casperjs en worker remoto
            else:
                for mention in pending_mentions:
                    do_process_mention(mention.pk)
        else:
            if Tweet.objects.filter(sending=False, sent_ok=False).exists():
                if bot:
                    raise NoAvailableBot(bot)
                else:
                    raise NoAvailableBots
            else:
                raise EmptyMentionQueue(bot=bot)


    def perform_sending_tweets(self, bot=None, max_tweets=None, max_lookups=None):
        """Mira n veces (max_lookups) en la cola de menciones cada x segundos y encola tweets a enviar"""

        def check_task_result(task):
            if task.failed():
                settings.LOGGER.warning('-- Task %s failed' % task.task_id)
            elif task.result:
                host, output = task.result
                settings.LOGGER.info('-- Task %s processed. host: %s, output: %s' % (task.task_id, host, output))
            celery_tasks.remove(task)

        from project.management.commands.tweet_sender import celery_tasks

        for l in xrange(max_lookups or 1):
            settings.LOGGER.info('LOOKUP %d' % (l+1))
            try:
                self.queue_tasks_from_mention_queue(max_tweets=max_tweets, bot=bot)
            except (EmptyMentionQueue,
                    NoAvailableBot,
                    NoAvailableBots):
                pass

            # antes de pasar al siguiente lookup vemos las tareas que se hayan terminado
            for task in celery_tasks:
                if task.ready():
                    check_task_result(task)

            time.sleep(settings.TIME_WAITING_NEXT_LOOKUP)

        # aquí esperamos a que terminen las pendientes antes de finalizar el tweet sender
        settings.LOGGER.info('Waiting completing tasks to finish tweet_sender..')
        has_to_wait = True
        while has_to_wait:
            has_to_wait = False
            for task in celery_tasks:
                if not task.ready():
                    has_to_wait = True
                    time.sleep(5)
                    settings.LOGGER.info('%i tasks remaining, waiting..' % len(celery_tasks))
                    break
                else:
                    check_task_result(task)

    def finish_creations(self, num_threads=None, num_tasks=None, bot=None):
        """Mira qué robots aparecen incompletos y termina de hacer en cada uno lo que quede"""
        from project.models import ProxiesGroup

         # ponemos a false todos los is_being_created
        self.put_previous_being_created_to_false()

        bots_to_finish_creation = self.pendant_to_finish_creation()  # sólo se eligen bots de grupos activos
        if bots_to_finish_creation.exists():
            if bot:
                try:
                    bot = bots_to_finish_creation.get(username=bot)
                    bot.complete_creation()
                except self.model.DoesNotExist:
                    bot = self.get(username=bot)
                    bot.log_reason_to_not_complete_creation()
            else:
                # si son varios a terminar, elegimos sólo uno por subnet
                if bots_to_finish_creation.count() > 1:
                    bots_to_finish_creation = bots_to_finish_creation.one_per_subnet()

                bots_to_finish_creation = bots_to_finish_creation[:num_tasks] if num_tasks else bots_to_finish_creation

                if num_threads == 1 or not num_threads:
                    for bot in bots_to_finish_creation:
                        bot.complete_creation()
                else:
                    pool = ThreadPool(num_threads or settings.MAX_THREADS_COMPLETING_PENDANT_BOTS)
                    # ponemos bots sin subnets repetidas para evitar varios registros desde misma subnet
                    for bot in bots_to_finish_creation:
                        pool.add_task(bot.complete_creation)
                    pool.wait_completion()

            settings.LOGGER.info('Sleeping %d seconds to respawn bot_creation_finisher again..' %
                                 settings.TIME_SLEEPING_FOR_RESPAWN_BOT_CREATION_FINISHER)
            time.sleep(settings.TIME_SLEEPING_FOR_RESPAWN_BOT_CREATION_FINISHER)
        else:
            settings.LOGGER.info('There is no more pendant bots to complete. Sleeping %d seconds for respawn..' %
                                 settings.TIME_SLEEPING_FOR_RESPAWN_BOT_CREATION_FINISHER)
            ProxiesGroup.objects.log_groups_with_creation_enabled_disabled()
            time.sleep(settings.TIME_SLEEPING_FOR_RESPAWN_BOT_CREATION_FINISHER)

    def check_proxies(self, bots):
        bots_without_proxy_ok = bots.without_proxy_ok()
        for bot in bots_without_proxy_ok:
            bot.assign_proxy()

    def get_distinct_proxies(self, bots):
        """Devuelve los distintos proxies que tienen los bots (se pasan por parámetro en formato queryset)"""
        from core.models import Proxy

        distinct_proxies = bots.values_list('proxy_for_usage__proxy', flat=True).distinct()
        return Proxy.objects.filter(proxy__in=distinct_proxies)

    #
    # Proxy methods to queryset
    #

    def get_queryset(self):
        return TwitterBotQuerySet(self.model, using=self._db)

    def without_any_account_registered(self):
        return self.get_queryset().without_any_account_registered()

    def usable_regardless_of_proxy(self):
        return self.get_queryset().usable_regardless_of_proxy()

    def unusable_regardless_of_proxy(self):
        return self.get_queryset().unusable_regardless_of_proxy()

    def registrable(self):
        return self.get_queryset().registrable()

    def with_valid_proxy_for_registration(self):
        return self.get_queryset().with_proxy_for_usage_ok_for_doing_registrations()

    def with_proxy_connecting_ok(self):
        return self.get_queryset().with_proxy_connecting_ok()

    def with_proxy_ok(self):
        return self.get_queryset().with_proxy_ok()

    def without_proxy_ok(self):
        return self.get_queryset().without_proxy_ok()

    def uncompleted(self):
        return self.get_queryset().unregistered()

    def registered_but_not_completed(self):
        return self.get_queryset().registered_but_not_completed()

    def completed(self):
        return self.get_queryset().completed()

    def twitteable_regardless_of_proxy(self):
        return self.get_queryset().twitteable_regardless_of_proxy()

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

    def pendant_to_finish_creation(self):
        return self.get_queryset().pendant_to_finish_creation()

    def mentioned_by_bot(self, bot):
        return self.get_queryset().mentioned_by_bot(bot)

    def unmentioned_by_bot(self, bot):
        return self.get_queryset().unmentioned_by_bot(bot)

    def one_per_subnet(self):
        return self.get_queryset().one_per_subnet()

    def annotate__mctweets_received_count(self):
        return self.get_queryset().annotate__mctweets_received_count()


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
            in_txts_proxies_count = 0  # cuenta el número de proxies que no aparecen en los txts
            db_proxies = self.all()
            for db_proxy in db_proxies:
                if is_on_txt(db_proxy):
                    db_proxy.is_in_proxies_txts = True
                    db_proxy.date_not_in_proxies_txts = None
                    db_proxy.save()
                    in_txts_proxies_count += 1
                    settings.LOGGER.info('Proxy %s remarked as appeared in proxies txts' % (db_proxy.__unicode__()))
                elif db_proxy.is_in_proxies_txts:
                    # si no está en los txt y estaba marcado como que estaba lo cambiamos
                    db_proxy.is_in_proxies_txts = False
                    db_proxy.date_not_in_proxies_txts = utc_now()
                    db_proxy.save()
                    not_in_txts_proxies_count += 1
                    settings.LOGGER.info('Proxy %s @ %s marked as not appeared in proxies txts' % (db_proxy.proxy, db_proxy.proxy_provider))

            settings.LOGGER.info('%i proxies marked as appeared in proxies txts' % in_txts_proxies_count)
            settings.LOGGER.info('%i proxies marked as not appeared in proxies txts' % not_in_txts_proxies_count)

        def add_new_proxies():
            settings.LOGGER.info('Adding new proxies to database..')
            new_count = 0
            for txt_proxy, txt_proxy_provider in txt_proxies:
                if txt_proxy and not self.filter(proxy=txt_proxy, proxy_provider=txt_proxy_provider).exists():
                    self.create(proxy=txt_proxy, proxy_provider=txt_proxy_provider)
                    settings.LOGGER.info('\tAdded new proxy %s @ %s' % (txt_proxy, txt_proxy_provider))
                    new_count += 1
            settings.LOGGER.info('%i new proxies added ok into database' % new_count)

        txt_proxies = self.get_txt_proxies()
        check_not_in_proxies_txts()
        add_new_proxies()

    def log_proxies_valid_for_assign_group(self):
        valid_proxies = self.valid_for_assign_proxies_group()
        if valid_proxies.exists():
            settings.LOGGER.warning('There are %d proxies available for group assignation' % valid_proxies.count())

    def get_subnets_24(self, proxies):
        """Devuelve las subredes /24 a las que pertenecen los proxies pasados por parámetro"""
        return list(set([proxy.get_subnet_24() for proxy in proxies.all()]))

    def mark_as_unavailable_for_use(self, proxies):
        proxies.update(
            is_unavailable_for_use=True,
            date_unavailable_for_use=utc_now()
        )

    def mark_as_available_for_use(self, proxies):
        proxies.update(
            is_unavailable_for_use=False,
            date_unavailable_for_use=None
        )


    #
    # PROXY QUERYSET
    #

    def get_queryset(self):
        return ProxyQuerySet(self.model, using=self._db)

    def connection_ok(self):
        return self.get_queryset().connection_ok()

    def connection_fail(self):
        return self.get_queryset().connection_fail()

    def available_to_assign_bots_for_use(self):
        return self.get_queryset().available_to_assign_bots_for_use()

    def unavailable_to_assign_bots_for_use(self):
        return self.get_queryset().unavailable_to_assign_bots_for_use()

    def available_to_assign_bots_for_registration(self):
        return self.get_queryset().available_to_assign_bots_for_registration()

    def unavailable_to_assign_bots_for_registration(self):
        return self.get_queryset().unavailable_to_assign_bots_for_registration()

    def without_any_dead_bot(self):
        return self.get_queryset().without_any_dead_bot()

    def with_some_dead_bot(self):
        return self.get_queryset().with_some_dead_bot()

    def using_in_running_projects(self):
        return self.get_queryset().using_in_running_projects()

    def without_bots(self):
        return self.get_queryset().without_bots()

    def for_group(self, group):
        return self.get_queryset().for_group(group)

    def with_some_suspended_bot(self):
        return self.get_queryset().with_some_suspended_bot()

    def without_any_suspended_bot(self):
        return self.get_queryset().without_any_suspended_bot()

    def with_proxies_group_enabling_bot_creation(self):
        return self.get_queryset().with_proxies_group_enabling_bot_creation()

    def with_proxies_group_enabling_bot_usage(self):
        return self.get_queryset().with_proxies_group_enabling_bot_usage()

    def valid_for_assign_proxies_group(self):
        return self.get_queryset().valid_for_assign_proxies_group()

    def invalid_for_assign_proxies_group(self):
        return self.get_queryset().invalid_for_assign_proxies_group()

    def with_completed_bots(self):
        return self.get_queryset().with_completed_bots()

    def without_completed_bots(self):
        return self.get_queryset().without_completed_bots()

    def with_distinct_subnets(self):
        return self.get_queryset().with_distinct_subnets()
