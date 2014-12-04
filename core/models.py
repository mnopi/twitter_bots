# -*- coding: utf-8 -*-
from django.db.models import Q
import feedparser
from django.contrib.auth.models import AbstractUser
from django.db import models
from project.exceptions import NoMoreAvailableProxiesForRegistration, BotHasNoProxiesForUsage, SuspendedBotHasNoProxiesForUsage, \
    TweetCreationException
from scrapper.accounts.hotmail import HotmailScrapper
from scrapper.exceptions import TwitterEmailNotFound, \
    TwitterAccountDead, TwitterAccountSuspended, ProfileStillNotCompleted
from scrapper.scrapper import Scrapper, INVALID_EMAIL_DOMAIN_MSG
from scrapper.accounts.twitter import TwitterScrapper
from core.managers import TwitterBotManager, ProxyManager
from twitter_bots import settings
from scrapper.utils import *


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
    has_fast_mode = models.BooleanField(default=False)
    user_agent = models.TextField(null=False, blank=True)

    email_registered_ok = models.BooleanField(default=False)
    twitter_registered_ok = models.BooleanField(default=False)
    twitter_confirmed_email_ok = models.BooleanField(default=False)
    twitter_avatar_completed = models.BooleanField(default=False)
    twitter_bio_completed = models.BooleanField(default=False)

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
        return settings.REGISTER_EMAIL and not self.email_registered_ok

    def has_to_register_twitter(self):
        return not self.twitter_registered_ok

    def has_to_confirm_tw_email(self):
        return not self.twitter_confirmed_email_ok

    def has_to_complete_tw_profile(self):
        return not self.has_tw_profile_completed()

    def has_to_set_tw_avatar(self):
        return not self.twitter_avatar_completed and settings.TW_SET_AVATAR

    def has_to_set_tw_bio(self):
        return not self.twitter_bio_completed and settings.TW_SET_BIO

    def has_to_complete_creation(self):
        return self.is_suspended or\
               not self.email_registered_ok or \
               not self.twitter_registered_ok or \
               not self.twitter_confirmed_email_ok or \
               not self.has_tw_profile_completed()

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
            available_proxies_for_reg = Proxy.objects.available_for_registration()
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

        def assign_new_proxy_for_usage():
            """
                Asignamos proxy entre los disponibles para el grupo del bot.
            """
            proxies = Proxy.objects.for_group(self.get_group()).available_for_usage()

            if self.was_suspended():
                # si fue suspendido le intentamos colar un proxy con bots también suspendidos
                proxies_available_with_suspended_bots = proxies.with_some_suspended_bot()
                if proxies_available_with_suspended_bots.exists():
                    self.proxy_for_usage = proxies_available_with_suspended_bots.order_by('?')[0]
                else:
                    # si no hay proxies disponibles que tengan bots suspendidos entonces sacamos los demás,
                    # incluídos los suspendidos si en el grupo se indicó reusar los proxies con robots suspendidos
                    proxies_available = proxies.filter_suspended_bots()
                    if proxies_available.exists():
                        self.proxy_for_usage = proxies_available.order_by('?')[0]
                    else:
                        raise SuspendedBotHasNoProxiesForUsage(self)
            else:
                proxies_available = proxies.filter_suspended_bots()
                if proxies_available.exists():
                    self.proxy_for_usage = proxies_available.order_by('?')[0]
                else:
                    raise BotHasNoProxiesForUsage(self)

        if self.has_to_register_twitter():
            assign_proxy_for_registration()
        else:
            assign_new_proxy_for_usage()
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
            settings.LOGGER.info('Completing creation for bot %s behind proxy %s' %
                                 (self.username, self.proxy_for_usage.__unicode__()))

            # eliminamos el directorio de capturas previas para el usuario
            rmdir_if_exists(os.path.join(settings.SCREENSHOTS_DIR, self.real_name))

            if settings.FAST_MODE and not settings.TEST_MODE:
                settings.LOGGER.warning('Fast mode only avaiable on test mode!')
                settings.FAST_MODE = False

            try:
                # init scrappers
                self.twitter_scr = TwitterScrapper(self)
                self.twitter_scr.open_browser()

                if self.has_to_register_email() or self.has_to_confirm_tw_email():
                    self.twitter_scr.check_proxy_works_ok()
                    self.email_scr = self.get_email_scrapper()
                    self.email_scr.open_browser()

                # 1_signup_email
                if self.has_to_register_email():
                    self.email_scr.set_screenshots_dir('1_signup_email')
                    try:
                        self.email_scr.sign_up()
                    except Exception as ex:
                        settings.LOGGER.exception('Error on bot %s registering email %s' %
                                                  (self.username, self.email))
                        self.email_scr.take_screenshot('signup_email_failure', force_take=True)
                        raise ex
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
                        self.twitter_scr.login()
                        self.email_scr.confirm_tw_email()
                        self.twitter_confirmed_email_ok = True
                        self.save()
                    except Exception as ex:
                        settings.LOGGER.exception('Error on bot %s confirming email %s' %
                                                  (self.username, self.email))
                        self.email_scr.take_screenshot('tw_email_confirmation_failure', force_take=True)
                        raise ex

                # 4_profile_completion
                if not self.has_to_confirm_tw_email() and self.has_to_complete_tw_profile():
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

            except (SuspendedBotHasNoProxiesForUsage,
                    BotHasNoProxiesForUsage,
                    ProfileStillNotCompleted,
                    NoMoreAvailableProxiesForRegistration,
                    TwitterAccountDead,
                    TwitterAccountSuspended):
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
            self.has_fast_mode = settings.FAST_MODE
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
            random_seconds = random.randint(60*settings.TIME_BETWEEN_TWEETS[0], 60*settings.TIME_BETWEEN_TWEETS[1])  # entre 2 y 7 minutos por tweet
            return (utc_now() - last_tweet.date_sent).seconds >= random_seconds
        else:
            # si el bot no tuiteo nunca evidentemente el tiempo no tiene nada que ver
            return True

    def is_already_sending_tweet(self):
        from project.models import Tweet
        return Tweet.objects.filter(bot_used=self, sending=True).exists()

    def can_tweet(self):
        """
        Devuelve si el bot puede tuitear, cumpliendo:
            - que no este el robot sending otro tweet
            - que no haya tuiteado entre random de 2 y 7 min (time_ok)
        """
        if not self.is_already_sending_tweet():
            return self.tweeting_time_interval_lapsed()
        else:
            return False

    def make_tweet_to_send(self, retry_counter=0):
        """Crea un tweet con mención pendiente de enviar"""
        from project.models import Tweet, TwitterUser

        # saco proyectos asignados para el robot que actualmente estén ejecutándose, ordenados de menor a mayor
        # número de tweets creados en la cola pendientes de enviar
        projects_with_this_bot = self.get_running_projects().order_by__queued_tweets()
        if projects_with_this_bot.exists():
            for project in projects_with_this_bot:

                # project.check_if_has_minimal_content()

                try:
                    tweet_to_send = Tweet(
                        project=project,
                        bot_used=self
                    )
                    tweet_to_send.save()
                    bot_group = self.get_group()

                    if bot_group.has_tweet_msg:
                        tweet_to_send.add_tweet_msg(project)
                        tweet_to_send.save()
                    if bot_group.has_link:
                        tweet_to_send.add_link(project)
                        tweet_to_send.save()
                    if bot_group.has_tweet_img:
                        tweet_to_send.add_image(project)
                        tweet_to_send.save()
                    if bot_group.has_page_announced:
                        tweet_to_send.add_page_announced(project)
                        tweet_to_send.save()
                    if bot_group.has_mentions:
                        tweet_to_send.add_mentions(self, project)

                    # tras encontrar ese proyecto con el que hemos podido construir el tweet salimos para
                    # dar paso al siguiente bot
                    break
                except TweetCreationException:
                    continue
        else:
            settings.LOGGER.warning('Bot %s has no running projects assigned at this moment' % self.__unicode__())

    def make_feed_tweet_to_send(self):
        "Crea un tweet a partir de algún feed pendiente de enviar"
        from project.models import Project, Tweet, TweetMsg, Link

        feed = feedparser.parse('http://feeds.feedburner.com/cuantogato?format=xml')
        entry = random.choice(feed['entries'])

        project = Project.objects.first()
        tweet_msg = TweetMsg.objects.create(text=entry['title'])
        link = Link.objects.create(url=entry['feedburner_origlink'])

        tweet_to_send = Tweet.objects.create(
            project=project,
            tweet_msg=tweet_msg,
            link=link,
            bot_used=self,
        )

        settings.LOGGER.info('Queued (project: %s, bot: %s) >> %s' %
                             (project.__unicode__(), self.__unicode__(), tweet_to_send.compose()))


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
    proxies_group = models.ForeignKey('project.ProxiesGroup', related_name='proxies', null=True, blank=True)

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