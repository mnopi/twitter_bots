# -*- coding: utf-8 -*-
import os
import time
import threading
import datetime

from django.db import models
import pytz
from project.exceptions import BotNotFoundException
from scrapper.exceptions import BotDetectedAsSpammerException, NoMoreAvaiableProxiesException, \
    FailureSendingTweetException
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

    def get_valid_bot(self, **kwargs):
        """
        De todo el conjunto de bots, escoge el primer bot considerado válido:
            -   que no haya tuiteado como mínimo entre tiempo random 2-5 minutos
            -   en caso de ser varios se coge al del tuit más antiguo
        """
        kwargs.update({
            'it_works': True,

        })
        bot = self.get_all_bots(**kwargs)[0]
        try:
            bot.scrapper.login()
            return bot
        except Exception:
            bot.mark_as_not_twitter_registered_ok()
            self.get_valid_bot(**kwargs)

    def get_bot_available_to_mention(self):
        from project.models import Project, TwitterUser, Tweet, Link

        for bot in self.get_all_bots().filter(it_works=True):
            if bot.can_tweet():
                for project in Project.objects.filter(is_running=True):

                    # solo cogemos los usuarios de las plataformas para el proyecto. Por ejemplo, si hay
                    # twitterusers de ios y no tenemos enlaces de ios, que no se envie a estos

                    # iterando por las plataformas de un proyecto de momento no hay prioridad
                    # y la primera será la primera que se le añada

                    for platform in project.get_platforms():
                        project_users = TwitterUser.objects.filter(follower__target_user__projects=project)
                        project_unmentioned_users = project_users.filter(mentions=None, source=platform)

                        # saco alguno que no fue mencionado por el bot
                        unmentioned_by_bot = project_unmentioned_users.exclude(mentions__bot_used=bot)
                        if unmentioned_by_bot.exists():
                            user_to_mention = unmentioned_by_bot.first()
                            tweet_with_mention = Tweet(
                                project=project,
                                tweet_msg=project.tweet_msgs.order_by('?')[0],
                                link=project.links.filter(platform=user_to_mention.source).order_by('?')[0],
                                bot_used=bot,
                                sending=True,
                            )
                            tweet_with_mention.save()
                            tweet_with_mention.mentioned_users.add(user_to_mention)
                            return bot, tweet_with_mention

        raise BotNotFoundException()


    def get_all_bots(self):
        """Escoge todos aquellos bots que tengan phantomJS"""
        return self.filter(webdriver='PH').exclude(proxy='tor')

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
        def unlock_mutex():
            try:
                settings.LOGGER.info('%s mutex releasing..' % thread_name)
                mutex.release()
                settings.LOGGER.info('%s mutex released ok' % thread_name)
            except Exception as ex:
                settings.LOGGER.exception('%s error releasing mutex' % thread_name)

        tweet = bot = tweet_msg = None
        thread_name = '###%s### - ' % threading.current_thread().name

        try:
            mutex.acquire()

            # ESCOGEMOS ROBOT Y TWEET
            bot, tweet = self.get_bot_available_to_mention()
            tweet_msg = tweet.compose()
        finally:
            # QUITAMOS CANDADO
            unlock_mutex()

        try:
            settings.LOGGER.info('%s Bot %s sending tweet: "%s"' % (thread_name, bot.username, tweet_msg))
                bot.scrapper.set_screenshots_dir(str(tweet.pk))
            bot.scrapper.open_browser()
            bot.scrapper.login()
            bot.scrapper.send_tweet(tweet_msg)
            tweet.sending = False
            tweet.sent_ok = True
            tweet.date_sent = datetime.datetime.now()
            tweet.save()
            settings.LOGGER.info('Bot %s sent tweet ok: "%s"' % (bot.username, tweet_msg))
        except Exception as ex:
            try:
                settings.LOGGER.exception('%s Error sending tweet' % thread_name)
                if type(ex) is FailureSendingTweetException:
                    tweet.delete()
            except Exception as ex:
                settings.LOGGER.exception('%s Error catching exception' % thread_name)
                raise ex
            raise ex
        finally:
            bot.scrapper.close_browser()

    def send_tweets(self):
        from project.models import Tweet
        Tweet.objects.clean_not_sent_ok()
        settings.LOGGER.info('--- Trying to send %i tweets ---' % settings.MAX_THREADS_SENDING_TWEETS)

        threads = []
        for n in range(settings.MAX_THREADS_SENDING_TWEETS):
            thread = threading.Thread(target=self.send_tweet)
            thread.start()
            threads.append(thread)

        # to wait until all three functions are finished
        for thread in threads:
            thread.join()

        # pool = ThreadPool(settings.MAX_THREADS)
        # for _ in pending_tweets:
        # while True:
        # for _ in pending_tweets:
        #     LOGGER.info('Adding task..')
        #     pool.add_task(self.send_tweet)
        #     LOGGER.info('Checking if all tweets sent..')
        #     if Tweet.objects.all_sent_ok():
        #         break
        #     else:
        #         time.sleep(0.3)
        # pool.wait_completion()

    # def process_all_bots(self):
    #     bots = self.get_all_bots()
    #     settings.LOGGER.info('Processing %i bots..' % bots.count())
    #     pool = ThreadPool(settings.MAX_THREADS_CREATING_BOTS)
    #     for bot in bots:
    #         pool.add_task(bot.process, ignore_exceptions=True)
    #     pool.wait_completion()
    #     settings.LOGGER.info('%i bots processed ok' % bots.count())


