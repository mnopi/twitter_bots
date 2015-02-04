# -*- coding: utf-8 -*-
from django.db.models import Q, Count
import feedparser
from django.contrib.auth.models import AbstractUser
from django.db import models
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from project.exceptions import NoMoreAvailableProxiesForRegistration, NoAvailableProxiesToAssignBotsForUse,\
    TweetCreationException, LastMctweetFailedTimeWindowNotPassed
from core.scrapper.scrapper import Scrapper, INVALID_EMAIL_DOMAIN_MSG
from core.scrapper.accounts.hotmail import HotmailScrapper
from core.scrapper.accounts.twitter import TwitterScrapper
from core.scrapper.exceptions import TwitterEmailNotFound, \
    TwitterAccountDead, TwitterAccountSuspended, ProfileStillNotCompleted, FailureReplyingMcTweet, \
    TwitterEmailNotConfirmed, HotmailAccountNotCreated, EmailExistsOnTwitter
from core.scrapper.utils import *
from core.managers import TwitterBotManager, ProxyManager, mutex
from project.models import TwitterBotFollowing
from twitter_bots import settings
from django.core.exceptions import ObjectDoesNotExist


class User(AbstractUser):
    pass


class TwitterBot(models.Model):
    real_name = models.CharField(max_length=50, null=False, blank=True)
    email = models.CharField(max_length=256, null=False, blank=True)
    password_twitter = models.CharField(max_length=20, null=False, blank=True)
    password_email = models.CharField(max_length=20, null=False, blank=True)
    username = models.CharField(max_length=50, null=False, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    birth_date = models.DateField(null=True, blank=True)
    # LOCATIONS = {
    #     (0, 'USA'),
    #     (1, 'Europe'),
    #     (2, 'Asia'),
    # }
    # location = models.IntegerField(max_length=1, choices=LOCATIONS, default=0)

    GENDERS = {
        (0, 'male'),
        (1, 'female'),
    }
    gender = models.IntegerField(max_length=1, choices=GENDERS, default=0)

    is_dead = models.BooleanField(default=False)
    date_death = models.DateTimeField(null=True, blank=True)

    is_suspended = models.BooleanField(default=False)
    date_suspended_twitter = models.DateTimeField(null=True, blank=True)
    # guardamos cuántas veces se ha levantado la suspensión del bot en twitter
    num_suspensions_lifted = models.PositiveIntegerField(default=0)

    is_suspended_email = models.BooleanField(default=False)
    date_suspended_email = models.DateTimeField(null=True, blank=True)

    is_being_created = models.BooleanField(default=True)
    is_manually_registered = models.BooleanField(default=False)
    user_agent = models.TextField(null=False, blank=True)

    email_registered_ok = models.BooleanField(default=False)
    twitter_registered_ok = models.BooleanField(default=False)
    twitter_confirmed_email_ok = models.BooleanField(default=False)
    twitter_avatar_completed = models.BooleanField(default=False)
    twitter_bio_completed = models.BooleanField(default=False)

    # si está siguiendo ahora a gente y cuando fue la última vez que terminó de ponerse a seguir
    is_following = models.BooleanField(default=False)
    date_last_following = models.DateTimeField(null=True, blank=True)
    following_ratio = models.DecimalField(null=True, blank=True, max_digits=2, decimal_places=1)

    # RELATIONSHIPS
    proxy_for_registration = models.ForeignKey('Proxy', null=True, blank=True, related_name='twitter_bots_registered', on_delete=models.DO_NOTHING)
    proxy_for_usage = models.ForeignKey('Proxy', null=True, blank=True, related_name='twitter_bots_using', on_delete=models.DO_NOTHING)

    # objects = TwitterBotManager(TwitterBotQuerySet)
    objects = TwitterBotManager()

    def __unicode__(self):
        return self.username

    def __init__(self, *args, **kwargs):
        super(TwitterBot, self).__init__(*args, **kwargs)
        self.scrapper = TwitterScrapper(self)

    def has_no_accounts(self):
        return not self.email_registered_ok and not self.twitter_registered_ok

    def has_to_register_email(self):
        return not self.email_registered_ok

    def has_to_register_twitter(self):
        return not self.has_to_register_email() and not self.twitter_registered_ok

    def has_to_register_accounts(self):
        return not self.email_registered_ok and not self.twitter_registered_ok

    def has_to_confirm_tw_email(self):
        return not self.has_to_register_twitter() and not self.twitter_confirmed_email_ok

    def has_to_complete_tw_profile(self):
        return not self.has_to_confirm_tw_email() and not self.has_tw_profile_completed()

    def has_to_set_tw_avatar(self):
        return not self.twitter_avatar_completed and settings.TW_SET_AVATAR

    def has_to_set_tw_bio(self):
        return not self.twitter_bio_completed and settings.TW_SET_BIO

    def has_to_complete_creation(self):
        return self.is_suspended or\
               self.has_to_register_email() or \
               self.has_to_register_twitter() or \
               self.has_to_confirm_tw_email() or \
               self.has_to_complete_tw_profile()

    def has_tw_profile_completed(self):
        return not self.has_to_set_tw_avatar() and not self.has_to_set_tw_bio()

    def mark_as_suspended(self):
        """Se marca como suspendido y se eliminan todos los tweets en la cola pendientes de enviar por ese robot"""
        from project.models import Tweet

        self.is_suspended = True
        self.date_suspended = utc_now()
        self.save()
        Tweet.objects.filter(sent_ok=False, bot_used=self).delete()
        settings.LOGGER.warning('User %s has marked as suspended on twitter. Tweet to send queue cleaned for him' % self.username)

    def unmark_as_suspended(self):
        self.is_suspended = False
        self.date_suspended = None
        self.num_suspensions_lifted += 1
        self.save()
        settings.LOGGER.info('User %s has lift suspension on his twitter account' % self.username)

    def mark_as_not_twitter_registered_ok(self):
        self.twitter_registered_ok = False
        self.twitter_confirmed_email_ok = False
        self.it_works = False
        self.save()
        settings.LOGGER.warning('User %s has marked as not twitter registered ok' % self.username)

    def get_email_username(self):
        """Pilla el usuario de ese email (sin el @etc.com)"""
        return self.email.split('@')[0]

    def get_email_account_domain(self):
        """Pilla el dominio de ese email (por ejemplo @gmail.com)"""
        return self.email.split('@')[1]

    def proxy_works_ok(self):
        """Mira si el proxy que el bot tiene asignado funciona correctamente"""
        Scrapper(self).check_proxy_works_ok()

    def assign_proxy(self):
        """
            Al bot se le asigna un proxy disponible según tenga cuentas ya creadas o no
        """
        from project.models import Project

        def assign_proxy_for_registration():
            """
                Asignamos proxy para registro, el cual será el mismo que para el uso
            """
            available_proxies_for_reg = Proxy.objects.available_to_assign_bots_for_registration()
            if not available_proxies_for_reg.exists():
                raise NoMoreAvailableProxiesForRegistration()
            else:
                if settings.PRIORIZE_RUNNING_PROJECTS_FOR_BOT_CREATION:
                    proxies_running = available_proxies_for_reg.using_in_running_projects()
                    if proxies_running.exists():
                        self.proxy_for_registration = proxies_running.order_by('?')[0]
                    else:
                        settings.LOGGER.warning('No proxies assignable for registration on %d running projects' %
                                                Project.objects.running().count())
                        self.proxy_for_registration = available_proxies_for_reg.order_by('?')[0]
                else:
                    self.proxy_for_registration = available_proxies_for_reg.order_by('?')[0]

                self.proxy_for_usage = self.proxy_for_registration

        def assign_proxy_for_usage():
            """
                Asignamos proxy entre los disponibles para el grupo del bot.
            """
            proxies = Proxy.objects.for_group(self.get_group()).available_to_assign_bots_for_use()
            if proxies.exists():
                if self.was_suspended():
                    # si el bot fue suspendido le intentamos colar un proxy con bots también suspendidos
                    proxies_available_with_suspended_bots = proxies.with_some_suspended_bot()
                    if proxies_available_with_suspended_bots.exists():
                        self.proxy_for_usage = proxies_available_with_suspended_bots.order_by('?')[0]
                    else:
                        # si no hay proxies con bots suspendidos entonces lo meteremos en proxies sin suspendidos
                        # según se indicara en la opción de reusar proxies con bots suspendidos
                        proxies_f_suspended = proxies.filter_suspended_bots()
                        if proxies_f_suspended.exists():
                            self.proxy_for_usage = proxies_f_suspended.order_by('?')[0]
                        else:
                            raise NoAvailableProxiesToAssignBotsForUse(self)
                else:
                    self.proxy_for_usage = proxies.order_by('?')[0]
            else:
                raise NoAvailableProxiesToAssignBotsForUse(self)

            settings.LOGGER.info('Assigned proxy for usage %s to bot %s' % (self.proxy_for_usage, self.username))

        if self.has_to_register_accounts():
            assign_proxy_for_registration()
        else:
            assign_proxy_for_usage()
        self.save()

    def get_email_scrapper(self):
        email_domain = self.get_email_account_domain()
        if email_domain == 'hotmail.com' or email_domain == 'outlook.com':
            return HotmailScrapper(self)
        else:
            raise Exception(INVALID_EMAIL_DOMAIN_MSG)

    def complete_creation(self):
        if self.has_to_complete_creation():
            t1 = utc_now()
            settings.LOGGER.info('Completing creation for bot %s (%s) behind proxy %s' %
                                 (self.username, self.real_name, self.proxy_for_usage.__unicode__()))

            # eliminamos el directorio de capturas previas para el usuario
            rmdir_if_exists(os.path.join(settings.SCREENSHOTS_DIR, self.real_name))

            try:
                # init scrappers
                self.twitter_scr = TwitterScrapper(self)
                self.twitter_scr.open_browser()

                if self.has_to_register_email() or self.has_to_register_twitter() or self.has_to_confirm_tw_email():
                    self.twitter_scr.check_proxy_works_ok()
                    self.email_scr = self.get_email_scrapper()
                    self.email_scr.open_browser()

                # 1_signup_email
                if self.has_to_register_email():
                    self.email_scr.set_screenshots_dir('1_signup_email')
                    self.email_scr.sign_up()
                    self.email_registered_ok = True
                    self.save()
                    self.email_scr.take_screenshot('signed_up_sucessfully', force_take=True)
                    self.email_scr.delay.seconds(7)
                    self.email_scr.logger.info('%s signed up ok' % self.email)

                # 2_signup_twitter
                if self.has_to_register_twitter():
                    self.twitter_scr.set_screenshots_dir('2_signup_twitter')
                    self.twitter_scr.sign_up()

                # 3_confirm_tw_email
                if self.has_to_confirm_tw_email():
                    self.email_scr.set_screenshots_dir('3_confirm_tw_email')
                    try:
                        self.email_scr.confirm_tw_email()
                        self.twitter_confirmed_email_ok = True
                        self.save()
                        self.email_scr.delay.seconds(8)
                        settings.LOGGER.info('Confirmed twitter email %s for user %s' % (self.email, self.username))
                        self.email_scr.take_screenshot('tw_email_confirmed_sucessfully', force_take=True)
                    except TwitterEmailNotFound:
                        self.twitter_scr.set_screenshots_dir('resend_conf_email')
                        try:
                            # nos logueamos para volver a pedir el email de confirmación
                            self.twitter_scr.login()
                        except TwitterEmailNotConfirmed:
                            pass
                        self.email_scr.confirm_tw_email()
                        self.twitter_confirmed_email_ok = True
                        self.save()
                        settings.LOGGER.info('Confirmed twitter email %s for user %s after resending confirmation' % (self.email, self.username))
                    except Exception as ex:
                        settings.LOGGER.exception('Error on bot %s confirming email %s' %
                                                  (self.username, self.email))
                        self.email_scr.take_screenshot('tw_email_confirmation_failure', force_take=True)
                        raise ex

                # 4_profile_completion
                if self.has_to_complete_tw_profile():
                    self.twitter_scr.set_screenshots_dir('4_tw_profile_completion')
                    self.twitter_scr.set_profile()

                # 5_lift_suspension
                if self.is_suspended:
                    settings.LOGGER.info('Lifting suspension for bot %s' % self.username)
                    self.twitter_scr.set_screenshots_dir('5_tw_lift_suspension')
                    self.twitter_scr.login()

                t2 = utc_now()
                diff_secs = (t2 - t1).seconds
                if self.has_to_complete_creation():
                    settings.LOGGER.info('Bot "%s" processed incompletely in %s seconds' % (self.username, diff_secs))
                else:
                    settings.LOGGER.info('Bot "%s" completed sucessfully in %s seconds' % (self.username, diff_secs))

            except (TwitterAccountSuspended,
                    HotmailAccountNotCreated,
                    NoAvailableProxiesToAssignBotsForUse,
                    ProfileStillNotCompleted,
                    NoMoreAvailableProxiesForRegistration,
                    TwitterAccountDead,
                    TwitterEmailNotConfirmed,
                    EmailExistsOnTwitter):
                pass
            except Exception as ex:
                settings.LOGGER.exception('Error completing creation for bot %s' % self.username)
                raise ex
            finally:
                # cerramos las instancias abiertas
                try:
                    if hasattr(self, 'email_scr'):
                        self.email_scr.close_browser()
                    self.twitter_scr.close_browser()
                    self.is_being_created = False
                    self.save()
                except Exception as ex:
                    settings.LOGGER.exception('Error closing browsers instances for bot %s' % self.username)
                    raise ex

    def generate_email(self):
        self.email = generate_random_username(self.real_name) + '@' + settings.EMAIL_ACCOUNT_TYPE

    def populate(self):
        try:
            self.gender = random.randint(0, 1)

            gender_str = 'female' if self.gender == 1 else 'male'
            self.real_name = names.get_full_name(gender=gender_str)
            self.generate_email()
            self.username = generate_random_username(self.real_name)
            self.password_email = generate_random_string()
            self.password_twitter = generate_random_string(only_lowercase=True)
            self.birth_date = random_date(settings.BIRTH_INTERVAL[0], settings.BIRTH_INTERVAL[1])
            self.user_agent = generate_random_desktop_user_agent()
            self.random_offsets = settings.RANDOM_OFFSETS_ON_EL_CLICK
            self.assign_proxy()
            self.save()
            settings.LOGGER.info('Bot %s populated with proxy %s' %
                                 (self.username, self.proxy_for_usage.__unicode__()))
        except Exception as ex:
            settings.LOGGER.exception('Error populating bot')
            raise ex

    def set_tw_profile(self):
        """Se completa avatar y bio en su perfil de twitter"""
        self.scrapper.open_browser()
        self.scrapper.set_profile()
        self.scrapper.close_browser()

    def get_users_mentioned(self):
        "Devuelve todos los usuarios que ha mencionado el robot a lo largo de todos sus tweets"
        from project.models import TwitterUser
        return TwitterUser.objects.filter(mentions__bot_used=self)

    def already_mentions(self, tweet):
        """Si el robot ya menciono alguno de los usuarios en el tweet dado"""
        all_bot_mentions = self.get_users_mentioned()
        for tw_mention in tweet.mentioned_users.all():
            for b_mention in all_bot_mentions:
                if tw_mention.twitter_id == b_mention.twitter_id:
                    return True
        return False

    def get_sent_ok_tweets(self):
        from project.models import Tweet
        return Tweet.objects.filter(bot_used=self, sent_ok=True)

    def get_running_projects(self):
        """Saca los proyectos asignados a los grupos que pertenece el bot"""
        from project.models import Project
        return Project.objects.running().with_bot(self)

    def get_group(self):
        if self.proxy_for_usage:
            return self.proxy_for_usage.proxies_group
        else:
            return None

    def get_webdriver(self):
        if not self.proxy_for_usage or not self.proxy_for_usage.proxies_group:
            return None
        else:
            return self.proxy_for_usage.proxies_group.webdriver

    def tweeting_time_interval_lapsed(self):
        "Mira si ha pasado el suficiente tiempo desde la ultima vez que tuiteo"
        bot_tweets = self.get_sent_ok_tweets()
        if bot_tweets:
            last_tweet = bot_tweets.latest('date_sent')
            random_seconds = generate_random_secs_from_minute_interval(self.get_group().time_between_tweets)
            return (utc_now() - last_tweet.date_sent).seconds >= random_seconds
        else:
            # si el bot no tuiteo nunca evidentemente el tiempo no tiene nada que ver
            return True

    def is_already_sending_tweet(self):
        from project.models import Tweet
        return Tweet.objects.filter(bot_used=self, sending=True).exists()

    def is_already_checking_mention(self):
        from project.models import TweetCheckingMention
        return TweetCheckingMention.objects.filter(
            destination_bot_is_checking_mention=True,
            tweet__mentioned_bots=self
        ).exists()

    def is_already_being_used(self):
        return self.is_already_sending_tweet() or self.is_already_checking_mention() or self.is_following

    def can_tweet(self):
        """Nos dice si el bot puede tuitear"""

        # no podrá tuitear si está siendo usado
        if self.is_already_being_used():
            return False
        # tampoco si no pasó el tiempo suficiente desde que envió el último tweet
        elif not self.has_enough_time_passed_since_his_last_tweet():
            return False
        else:
            return True

    def make_mctweet_to_send(self):
        """
        Crea tweet para enviar a otro bot
        """
        from project.models import Tweet

        tweet_to_send = Tweet(
            bot_used=self,
            feed_item=self.get_item_to_send()
        )
        tweet_to_send.save()
        tweet_to_send.add_bot_to_mention()

        # todo: cambiar esto para alternar links de feeds con links de proyectos del bot
        # bot_to_mention = tweet_to_send.mentioned_bots.first()
        #
        # # iteramos por los proyectos del bot buscando algún link que no se le haya enviado
        # projects_with_this_bot = self.get_running_projects().order_by__queued_tweets()
        # if projects_with_this_bot.exists():
        #     for project in projects_with_this_bot:
        #         try:
        #             # miramos links
        #             # for link in project.links.all():
        #                 # if self.has_passed_timewindow_to_send_same_link(bot_to_mention, link)
        #             if project.links.exists():
        #                 tweet_to_send.add_link(project)
        #                 tweet_to_send.project = project
        #                 break
        #             elif project.pagelinks.exists():
        #                 tweet_to_send.add_page_announced(project)
        #                 tweet_to_send.project = project
        #                 break
        #         except TweetCreationException:
        #             continue
        #     tweet_to_send.save()
        # else:
        #     settings.LOGGER.warning('Bot %s has no running projects assigned at this moment' % self.__unicode__())

        return tweet_to_send

    def make_ftweet_to_send(self):
        from project.models import Tweet

        tweet_to_send = Tweet(
            bot_used=self,
            feed_item=self.get_item_to_send()
        )
        tweet_to_send.save()
        return tweet_to_send

    def make_mutweet_to_send(self):
        """Crea un tweet con mención pendiente de enviar"""
        from project.models import Tweet, TwitterUser

        tweet_to_send = None

        # saco proyectos asignados para el robot que actualmente estén ejecutándose, ordenados de menor a mayor
        # número de tweets creados en la cola pendientes de enviar
        projects_with_this_bot = self.get_running_projects().order_by__queued_tweets()
        if projects_with_this_bot.exists():
            for project in projects_with_this_bot:
                try:
                    tweet_to_send = Tweet(
                        project=project,
                        bot_used=self
                    )
                    tweet_to_send.save()

                    bot_group = self.get_group()
                    if bot_group.has_tweet_msg:
                        tweet_to_send.add_tweet_msg(project)
                    if bot_group.has_link:
                        tweet_to_send.add_link(project)
                    if bot_group.has_tweet_img:
                        tweet_to_send.add_image(project)
                    if bot_group.has_page_announced:
                        tweet_to_send.add_page_announced(project)

                    if bot_group.has_mentions:
                        tweet_to_send.add_twitterusers_to_mention()
                    else:
                        tweet_to_send.delete()
                        raise Exception('Bot group %s has not market "has_mentions"' % bot_group.name)

                    # tras encontrar ese proyecto con el que hemos podido construir el tweet salimos del for
                    break
                except TweetCreationException:
                    settings.LOGGER.warning('Error creating tweet %i and will be deleted' % tweet_to_send.pk)
                    tweet_to_send.delete()
                    continue
        else:
            settings.LOGGER.warning('Bot %s has no running projects assigned at this moment' % self.__unicode__())

        return tweet_to_send

    def get_item_to_send(self):
        "Escoge algún feed que el bot todavía no haya enviado"

        from project.models import Project, Tweet, TweetMsg, Link, FeedItem

        # saco un item de los feeds disponibles para el grupo del bot
        # si ese item ya lo mandó el bot sacamos otro
        items_not_sent = self.get_feed_items_not_sent_yet()
        if not items_not_sent.exists():
            # Si no hay item se consultan todos los feeds hasta que se cree uno nuevo
            self.save_new_item_from_feeds()
            items_not_sent = self.get_feed_items_not_sent_yet()

        # volvemos a comprobar para ver si se añadió nuevo item desde feed
        if items_not_sent.exists():
            return items_not_sent.first()
        else:
            # en caso de enviarse todos los feeditems ordenamos de menor a mayor numero de tweets
            # que se enviaron para cada uno. si la cuenta es la misma ordenamos por date_created
            # (así evitamos problemas si date_sent=None)
            settings.LOGGER.debug('Bot %s has sent all feeditems, getting oldest sent available..' % self.username)
            return FeedItem.objects.sent_by_bot(self)\
                .annotate(tw_count=Count('tweets'))\
                .order_by('tw_count', 'tweets__date_created')\
                .first()

    def get_feed_items_not_sent_yet(self):
        """Mira en los feeds asignados al grupo de proxies para el bot e intenta sacar un item
        que todavía éste no haya enviado."""

        from project.models import FeedItem

        proxies_group_for_bot = self.get_group()
        pg_items = FeedItem.objects.filter(
            feed__feeds_groups__proxies_groups=proxies_group_for_bot,
        )
        items_not_sent_by_bot = pg_items\
            .exclude(Q(tweets__bot_used=self) & Q(tweets__sent_ok=True))

        return items_not_sent_by_bot

    def save_new_item_from_feeds(self):
        """Consulta en todos los feeds para el bot cual item no está en BD y lo guarda"""

        for feed in self.get_feeds().order_by('?'):
            new_item = feed.get_new_item()
            if new_item:
                new_item.save()
                break

    def get_feeds(self):
        """Saca los feeds disponibles para el bot"""

        from project.models import Feed

        return Feed.objects.filter(
            feeds_groups__proxies_groups=self.get_group(),
        )

    def send_tweet(self, tweet):
        try:
            self.scrapper.set_screenshots_dir(str(tweet.pk))
            self.scrapper.open_browser()
            self.scrapper.login()
            self.scrapper.send_tweet(tweet)
            tweet.sending = False
            tweet.sent_ok = True
            tweet.date_sent = utc_now()
            tweet.save()
        except Exception as e:
            tweet.delete()
            raise e
        finally:
            self.scrapper.close_browser()

    def get_last_tweet_sent(self):
        """
            Saca el último tweet enviado por el bot
            :return tweet último o None si nunca envió tweet
        """
        tweets_sent = self.get_sent_ok_tweets()
        if tweets_sent:
            return tweets_sent.latest('date_sent')
        else:
            return None

    def was_suspended(self):
        return self.is_suspended or self.num_suspensions_lifted > 0

    def proxy_is_ok(self):
        if not self.proxy_for_usage:
            settings.LOGGER.warning('Trying to assign proxy for bot %s' % self.__unicode__())
            return False
        elif not self.proxy_for_usage.is_in_proxies_txts:
            settings.LOGGER.warning('Proxy %s is no longer on txts. Trying to assign new one..' %
                                    self.proxy_for_usage.__unicode__())
            return False
        elif self.proxy_for_usage.is_unavailable_for_use:
            settings.LOGGER.warning('Proxy %s is unavailable for use. Trying to assign new one..' %
                                    self.proxy_for_usage.__unicode__())
            return False
        else:
            return True

    def check_proxy_ok(self):
        if not self.proxy_is_ok():
            self.assign_proxy()

    def get_mctweets_created(self):
        """Saca todos los mctweets creados para el bot"""
        return self.tweets.filter(mentioned_bots__isnull=False)

    def get_mctweets_verified(self):
        return self.get_mctweets_created()\
            .filter(
                sent_ok=True,
                tweet_checking_mention__destination_bot_checked_mention=True
        )

    def get_mctweets_verified_ok(self):
        """Saca todos los mctweets enviados y verificados ok por el bot destino"""
        return self.get_mctweets_verified()\
            .filter(tweet_checking_mention__mentioning_works=True)

    def get_consecutive_tweets_mentioning_twitterusers(self):
        """Cuenta el número de tweets lanzados a twitterusers desde el último mctweet verificado ok"""

        last_mctweet_ok = self.get_mctweets_verified_ok().last()
        if last_mctweet_ok:
            return self.tweets.sent_ok().filter(date_sent__gt=last_mctweet_ok.date_sent)
        else:
            return self.tweets.sent_ok()

    def has_reached_consecutive_twitteruser_mentions(self):
        """Mira si el robot ya superó el límite de menciones consecutivas sin comprobar si siguen
        funcionando las menciones"""

        return self.get_consecutive_tweets_mentioning_twitterusers().count() >= \
               self.get_group().num_consecutive_mentions_for_check_mentioning_works

    def clear_not_sent_ok_mc_tweets(self):
        """Se eliminan todos los mc tweets que el bot no haya enviado ok"""

        from project.models import Tweet

        Tweet.objects.filter(
            mentioned_bots__isnull=False,
            bot_used=self,
            sent_ok=False,
        ).delete()

    def clear_not_sent_ok_ftweets(self):
        """Se eliminan todos los mc tweets que el bot no haya enviado ok"""

        from project.models import Tweet

        Tweet.objects.filter(
            tweet_from_feed__isnull=False,
            bot_used=self,
            sent_ok=False,
        ).delete()

    def get_or_create_mctweet(self):
        """El bot busca su tweet de verificación (mentioning check tweet). Si no existe crea uno"""

        from project.models import Tweet, TweetCheckingMention

        # vemos si ya hay algún mctweet sin verificar
        mctweet_not_checked = Tweet.objects.mentioning_bots().by_bot(self).not_checked_if_mention_arrives_ok()
        if mctweet_not_checked.exists():
            if mctweet_not_checked.count() > 1:
                settings.LOGGER.warning('There were found multiple mentioning check tweets pending to send from '
                                      'bot %s and will be deleted' % self.username)
                self.clear_not_sent_ok_mc_tweets()
                self.make_mctweet_to_send()
        else:
            # si no existe dicho tweet de verificación el bot lo crea
            self.make_mctweet_to_send()

        mctweet = mctweet_not_checked.first()

        # si el mctweet no tiene asociado el registro tcm lo crea
        TweetCheckingMention.objects.get_or_create(tweet=mctweet)

        return mctweet

    def get_rest_of_bots_under_same_group(self):
        """Devuelve una lista de bots dentro de su mismo grupo de proxies (él no va incluido)"""
        group = self.get_group()

        return TwitterBot.objects\
            .using_proxies_group(group)\
            .twitteable_regardless_of_proxy()\
            .with_proxy_connecting_ok()\
            .exclude(pk=self.pk)

    def has_passed_timewindow_to_send_same_link(self, bot_to_mention, tweet):
        """Comprueba si pasó el tiempo suficiente para mandar mismo link a mismo bot"""

        # todo: por acabar
        # for bot in bots_under_same_group:
        #     # sacamos las menciones que este bot (self) hizo a cada bot
        #     mentions = bot.mentions.filter(bot_used=self)
        #     if mentions.exists():
        #         secs = generate_random_secs_from_minute_interval(group.mctweet_to_same_bot_time_window)
        #         time_window_passed = has_elapsed_secs_since_time_ago(
        #             mentions.latest('date_sent').date_sent,
        #             secs
        #         )
        #         if time_window_passed:
        #             final_bots.append(bot)
        #     else:
        #         final_bots.append(bot)

        raise NotImplementedError

    def has_enough_time_passed_since_his_last_tweet(self):
        """Nos dice si pasó el suficiente tiempo desde que el robot tuiteó por última vez a un usuario"""
        last_tweet_sent = self.get_last_tweet_sent()
        if not last_tweet_sent or not last_tweet_sent.date_sent:
            return True
        else:
            # si el bot ya envió algún tweet se comprueba que el último se haya enviado
            # antes o igual a la fecha de ahora menos el tiempo aleatorio entre tweets por bot
            random_seconds_ago = generate_random_secs_from_minute_interval(self.get_group().time_between_tweets)
            if is_lte_than_seconds_ago(last_tweet_sent.date_sent, random_seconds_ago):
                return True
            else:
                return False

    def check_if_can_send_mctweet(self):
        last_verified_mctweet = self.get_mctweets_verified().last()
        last_verified_mctweet_was_failed = last_verified_mctweet and \
                                           not last_verified_mctweet.tweet_checking_mention.mentioning_works
        if last_verified_mctweet_was_failed:
            # si el último mctweet falló su verificación vemos si pasó el tiempo de espera
            mentioning_fail_timewindow_is_passed = has_elapsed_secs_since_time_ago(
                last_verified_mctweet.tweet_checking_mention.destination_bot_checked_mention_date,
                generate_random_secs_from_minute_interval(self.get_group().mention_fail_time_window)
            )
            if not mentioning_fail_timewindow_is_passed:
                raise LastMctweetFailedTimeWindowNotPassed(self)

    def verify_tweet_if_received_ok(self, tweet):
        """Comprueba si le llegó ok la mención del tweet dado por parámetro"""

        def do_reply():
            def check_replied_ok():
                # comprobamos si se envió bien la respuesta
                try:
                    mention_received_ok_el.find_element_by_css_selector('ol.expanded-conversation')
                except NoSuchElementException:
                    raise FailureReplyingMcTweet(scr, tweet)

                settings.LOGGER.info('Bot %s replied ok "%s" to mention from %s' %
                                     (mentioned_bot.username, reply_msg, tweet.bot_used.username))
                scr.take_screenshot('mention_replied_ok', force_take=True)

            reply_btn = mention_received_ok_el.find_element_by_css_selector('.js-actionReply')
            scr.click(reply_btn)

            input_text = mention_received_ok_el.find_element_by_css_selector('#tweet-box-template')
            reply_msg = scr.get_random_reply()
            scr.fill_input_text(input_text, reply_msg)

            tweet_btn = mention_received_ok_el.find_element_by_css_selector('.tweet-button .btn')
            scr.click(tweet_btn)
            scr.delay.seconds(5)
            check_replied_ok()

        from project.models import TweetCheckingMention

        if not tweet.mentioned_bots.exists():
            raise Exception('You can\'t check mention over tweet %i without bot mentions' % tweet.pk)
        else:
            tcm = TweetCheckingMention.objects.get(tweet=tweet)
            try:
                # nos logueamos con el bot destino y comprobamos
                mentioned_bot = tweet.mentioned_bots.all()[0]
                settings.LOGGER.info('Bot %s verifying tweet sent from %s..' %
                                     (mentioned_bot.username, tweet.bot_used.username))
                scr = mentioned_bot.scrapper

                scr.set_screenshots_dir('checking_mention_%s_from_%s' % (tweet.pk, tweet.bot_used.username))
                scr.open_browser()
                scr.login()
                scr.click('li.notifications')
                scr.click('a[href="/mentions"]')

                # esto contendrá la cajita de la mención recibida
                mention_received_ok_el = None

                mentions_timeline_el = scr.get_css_elements('#stream-items-id > li')
                for mention_el in mentions_timeline_el:
                    # buscamos en la lista el último tweet enviado por ese bot
                    user_mentioning = mention_el.find_element_by_css_selector('.username.js-action-profile-name').text.strip('@')
                    user_mentioning_is_bot = TwitterBot.objects.filter(username=user_mentioning).exists()

                    if user_mentioning_is_bot:
                        if user_mentioning == tweet.bot_used.username:
                            # una vez que encontramos el último tweet enviado por ese bot vemos si coincide con el
                            # tweet que dice nuestra BD que se le mandó, sin contar con el link
                            mention_text = mention_el.find_element_by_css_selector('.js-tweet-text').text.strip()
                            if tweet.compose(with_link=False) in mention_text:
                                mention_received_ok_el = mention_el
                                break
                        else:
                            continue

                if mention_received_ok_el:
                    scr.take_screenshot('mention_arrived_ok', force_take=True)
                    settings.LOGGER.info('Bot %s received mention ok from %s' %
                                         (mentioned_bot.username, tweet.bot_used.username))
                    try:
                        do_reply()
                    except FailureReplyingMcTweet:
                        # de momento sólo sacamos mensajito si no se pudo responder
                        pass
                    tcm.mentioning_works = True
                else:
                    scr.take_screenshot('mention_not_arrived', force_take=True)
                    settings.LOGGER.error('Bot %s not received mention from %s tweeting: %s' %
                                          (mentioned_bot.username, tweet.bot_used.username, tweet.compose()))
                    tcm.mentioning_works = False

                tcm.destination_bot_checked_mention = True
                tcm.destination_bot_checked_mention_date = utc_now()
            finally:
                tcm.destination_bot_is_checking_mention = False
                tcm.save()

    def has_to_follow_people(self):
        """Nos dice si el robot tiene que ponerse a seguir gente, es decir, si su grupo está configurado
        para seguir gente y ha pasado el periodo ventana desde la última vez que se puso a seguir"""
        bot_group = self.get_group()
        if bot_group.has_following_activated:
            time_window_to_follow = bot_group.time_window_to_follow
            tw_secs = generate_random_secs_from_hour_interval(time_window_to_follow)
            return not self.date_last_following or \
                   has_elapsed_secs_since_time_ago(self.date_last_following, tw_secs)
        else:
            return False

    def follow_twitterusers(self):
        """Se pone el bot a seguir gente"""

        def get_ratio():

            def get_count(what):
                """Scrapea cuenta de seguidos o seguidores según se indique"""
                if what != 'following' and what != 'followers':
                    raise Exception('Invalid type to count (only accepts following/followers)')
                else:
                    el = scr.get_css_element('.ProfileNav-list .ProfileNav-item--%s .ProfileNav-value' % what)
                    if el:
                        return int(el.text)
                    else:
                        return 0

            # asignamos un ratio al bot si no se le asignó ya
            if not self.following_ratio:
                self.following_ratio = str_interval_to_random_double(self.get_group().following_ratio)
                self.save()

            num_following = get_count('following')
            num_followers = get_count('followers')

            if not num_following and not num_followers:
                # si no tiene gente siguiendo ni seguidores entonces el ratio será 0
                return 0
            elif num_following and not num_followers:
                # si tiene siguiendo pero sin seguidores el ratio será los que vaya siguiendo
                return num_following
            else:
                return num_following / num_followers

        def follow_twitteruser(twitteruser):
            try:
                scr.logger.debug('performing following %s' % twitteruser.username)

                scr.go_to(settings.URLS['twitter_login'] + twitteruser.username)

                # scr.fill_input_text('#search-query', '@' + twitteruser.username)
                #
                # # si el user está entre los posibles resultados..
                # twuser_on_minibox = scr.get_css_element('li[data-user-screenname="%s"]' % twitteruser.username)
                # if twuser_on_minibox:
                #     scr.move_mouse_to_el(twuser_on_minibox)
                #     scr.delay.seconds(2)
                #     ActionChains(scr.browser).click().perform()
                #
                # # si no aparece en la cajita damos enter y buscamos entre las personas..
                # else:
                #     scr.send_special_key(Keys.ENTER)
                #     scr.wait_to_page_readystate()
                #     scr.delay.seconds(3)
                #     search_people_btn_css = '.dashboard.dashboard-left li.search-navigation a[data-nav="users"]'
                #     scr.click(search_people_btn_css)
                #
                #     # miramos en cada uno de los resultados a ver cual es el usuario en cuestión @..
                #     search_people_results = scr.get_css_elements('ol#stream-items-id li')
                #     if search_people_results:
                #         for el in search_people_results:
                #             el_username = el.find_element_by_css_selector('span.username')
                #             if el_username and el_username.text.strip('@') == twitteruser.username:
                #                 scr.click(el_username)
                #                 break
                #     else:
                #         scr.take_screenshot('no_search_results_error')
                #         raise Exception('No search results for twuser %s' % twitteruser.username)

                # sale el perfil del twuser
                scr.delay.seconds(3)
                scr.wait_to_page_readystate()

                # ya en la página del perfil vemos si se está siguiendo o no, por si lo siguió pero no se guardó en BD
                follow_btn_css = 'li.ProfileNav-item.ProfileNav-item--userActions .follow-button'
                follow_btn_visible = scr.check_visibility('%s span.follow-text' % follow_btn_css)
                already_following_btn_visible = scr.check_visibility('%s span.following-text' % follow_btn_css)

                # se hará click sólo si no se dió antes, por si se dió pero no se guardó en BD
                if follow_btn_visible:
                    scr.click('%s span.follow-text' % follow_btn_css)
                    already_following_btn_visible = scr.check_visibility('%s span.following-text' % follow_btn_css)

                # una vez que ya aparece el botón de seguir como pulsado se guarda el seguimiento en BD
                if already_following_btn_visible:
                    tb_following = twitteruser.tb_followings.get(bot=self)
                    tb_following.performed_follow = True
                    tb_following.followed_ok = True
                    if not tb_following.date_followed:
                        tb_following.date_followed = utc_now()
                    tb_following.save()

                scr.delay.seconds(5)

                scr.take_screenshot('%s_followed_ok' % twitteruser.username)
                scr.logger.debug('%s followed ok' % twitteruser.username)
            except Exception as e:
                scr.take_screenshot('error_following_user_%s' % twitteruser.username)
                scr.logger.exception('Error following user %s' % twitteruser.username)
                raise e

        scr = self.scrapper
        scr.set_screenshots_dir('following_people_%s' % utc_now_to_str())

        try:
            scr.open_browser()
            scr.login()
            scr.click('.DashboardProfileCard-name a')

            # miramos qué ratio tiene de following/followers. Si inferior al del bot entonces
            # lo ponemos a seguir los que se marcaron como pendientes durante el mutex
            ratio = get_ratio()
            ratio_is_below = ratio < self.following_ratio
            if ratio_is_below:
                twusers_to_follow = self.get_twitterusers_to_follow_at_once()
                settings.LOGGER.info('Bot %s following %d twitterusers..' % (self.username, twusers_to_follow.count()))
                for twitteruser in twusers_to_follow:
                    follow_twitteruser(twitteruser)
                settings.LOGGER.info('Bot %s followed %d twitterusers ok' % (self.username, twusers_to_follow.count()))
            else:
                settings.LOGGER.info('%s not have to follow anyone for now. current ratio: %.1f, max ratio: %.1f' %
                                      (self.username, ratio, self.following_ratio))
            self.date_last_following = utc_now()
            self.save()
        except Exception as e:
            settings.LOGGER.exception('Error on bot %s following twitterusers' % self.username)
            raise e
        finally:
            scr.close_browser()

    def mark_twitterusers_to_follow_at_once(self):
        """Reserva dentro del mutex los twitterusers que el bot ha de seguir de una vez"""
        from project.models import TwitterUser

        # vemos si quedan seguimientos pendientes por hacer
        follows_pending = self.tb_followings.filter(performed_follow=False)
        if not follows_pending.exists():
            # si no quedaban pendientes sacamos un proyecto al azar donde opere su grupo de bots
            random_project = self.get_group().projects.order_by('?').first()

            # escogemos n twitterusers de ese proyecto que aún no hayan sido seguidos por ningún bot
            max_followings = str_interval_to_random_num(self.get_group().max_num_users_to_follow_at_once)
            twusers_to_follow = TwitterUser.objects\
                .for_project(random_project)\
                .not_followed()\
                .order_by('-last_tweet_date')\
                [:max_followings]

            following_entries = []
            for twuser in twusers_to_follow:
                following_entries.append(TwitterBotFollowing(bot=self, twitteruser=twuser))

            TwitterBotFollowing.objects.bulk_create(following_entries)

    def get_twitterusers_to_follow_at_once(self):
        """Saca twitterusers pendientes de ser seguidos por el bot"""

        from project.models import TwitterUser

        to_follow_pks = self.tb_followings.filter(performed_follow=False).values_list('twitteruser', flat=True)
        return TwitterUser.objects.filter(pk__in=to_follow_pks)

class Proxy(models.Model):
    proxy = models.CharField(max_length=21, null=False, blank=True)
    proxy_provider = models.CharField(max_length=50, null=False, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)

    is_in_proxies_txts = models.BooleanField(default=True)
    date_not_in_proxies_txts = models.DateTimeField(null=True, blank=True)

    # esto dice si está disponible para registrarse con hotmail/outlook
    is_unavailable_for_registration = models.BooleanField(default=False)
    date_unavailable_for_registration = models.DateTimeField(null=True, blank=True)

    is_unavailable_for_use = models.BooleanField(default=False)
    date_unavailable_for_use = models.DateTimeField(null=True, blank=True)

    is_phone_required = models.BooleanField(default=False)
    date_phone_required = models.DateTimeField(null=True, blank=True)

    # RELATIONSHIPS
    proxies_group = models.ForeignKey('project.ProxiesGroup', related_name='proxies', null=True, blank=True, on_delete=models.SET_NULL)

    objects = ProxyManager()

    class Meta:
        verbose_name_plural = "proxies"

    def __unicode__(self):
        group_str = self.proxies_group.__unicode__() if self.proxies_group else 'NO GROUP'
        return '%s @ %s :: %s' % (self.proxy, self.proxy_provider, group_str)

    def get_suspended_bots(self):
        return self.twitter_bots_using.filter(
            Q(is_suspended=True) |
            Q(num_suspensions_lifted__gt=0)
        ).distinct()

    def get_dead_bots(self):
        return self.twitter_bots_using.filter(is_dead=True).distinct()

    def get_ip(self):
        return self.proxy.split(':')[0]

    def get_port(self):
        return self.proxy.split(':')[1]

    def get_subnet_24(self):
        return '.'.join(self.get_ip().split('.')[:3])

    def mark_as_unavailable_for_use(self):
        if settings.MARK_PROXIES_AS_UNAVAILABLE_FOR_USE:
            self.is_unavailable_for_use = True
            self.date_unavailable_for_use = utc_now()
            self.save()
            settings.LOGGER.warning('Proxy %s marked as unavailable for use' % self.__unicode__())