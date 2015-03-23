# -*- coding: utf-8 -*-
from shutil import copyfile
from django.db.models import Q, Count, Sum
from django.contrib.auth.models import AbstractUser
from django.db import models, connection
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from project.exceptions import NoMoreAvailableProxiesForRegistration, NoAvailableProxiesToAssignBotsForUse,\
    TweetCreationException, LastMctweetFailedTimeWindowNotPassed, BotHasToWaitToRegister, CancelCreation
from core.scrapper.scrapper import Scrapper, INVALID_EMAIL_DOMAIN_MSG
from core.scrapper.accounts.hotmail import HotmailScrapper
from core.scrapper.accounts.twitter import TwitterScrapper
from core.scrapper.exceptions import *
from core.scrapper.utils import *
from core.managers import TwitterBotManager, ProxyManager, mutex
from project.models import TwitterBotFollowing
from twitter_bots import settings


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

    # phone
    is_phone_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=50, null=True, blank=True)

    is_dead = models.BooleanField(default=False)
    date_death = models.DateTimeField(null=True, blank=True)

    is_suspended = models.BooleanField(default=False)
    date_suspended_twitter = models.DateTimeField(null=True, blank=True)
    # guardamos cuántas veces se ha levantado la suspensión del bot en twitter
    num_suspensions_lifted = models.PositiveIntegerField(default=0)

    is_suspended_email = models.BooleanField(default=False)
    date_suspended_email = models.DateTimeField(null=True, blank=True)

    is_being_created = models.BooleanField(default=True)
    is_being_used = models.BooleanField(default=False)
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

    def has_ftweets_enabled(self):
        """Nos dice si el bot pertenece a un grupo que tenga habilitado el envío de ftweets,
        es decir, si el intervalo de ftweets por tweet es mayor que 0"""
        return str_interval_to_random_num(self.get_group().feedtweets_per_twitteruser_mention) > 0

    def mark_as_suspended(self):
        """Se marca como suspendido y se eliminan todos los tweets en la cola pendientes de enviar por ese robot"""
        from project.models import Tweet

        self.is_suspended = True
        self.date_suspended_twitter = utc_now()
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

    def assign_proxy(self, proxies_group=None):
        """
            Al bot se le asigna un proxy disponible según tenga cuentas ya creadas o no
        """
        from project.models import Project

        def assign_proxy_for_registration():
            """
                Asignamos proxy para registro, el cual será el mismo que para el uso
            """
            available_proxies_for_reg = Proxy.objects.available_to_assign_bots_for_registration()
            if proxies_group:
                available_proxies_for_reg = available_proxies_for_reg.filter(proxies_group=proxies_group)
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
                settings.LOGGER.info('Assigned proxy for registration/usage %s to bot %s' % (self.proxy_for_usage, self.username))

        def assign_proxy_for_usage():
            """
                Asignamos proxy entre los disponibles para el grupo del bot.
            """
            if proxies_group:
                proxies = Proxy.objects.for_group(proxies_group).available_to_assign_bots_for_use()
            else:
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

    def check_if_can_be_registered_on_hotmail(self):
        """Nos dice si el bot se registrar su cuenta email/twitter"""
        if not self.proxy_for_usage.can_register_bots_on_hotmail():
            raise BotHasToWaitToRegister(self, 'hotmail')

    def check_if_can_be_registered_on_twitter(self):
        """Nos dice si el bot se registrar su cuenta email/twitter"""
        if not self.proxy_for_usage.can_register_bots_on_twitter():
            raise BotHasToWaitToRegister(self, 'twitter')

    def complete_creation(self, first_time=False):
        """Hace los registros de email/twitter para el bot, confirma email en twitter y rellena perfil (avatar y bio).
        También intenta levantar suspensión si estaba suspendido"""

        def new_screenshots_dir(scrapper, name):
            """Crea carpetas en un orden numérico para meter ahí cada screenshot:
                1_trying_login_email
                2_..
                ...
            """
            dir_index[0] += 1
            scrapper.set_screenshots_dir('%d_%s' % (dir_index[0], name))

        def login_email_and_twitter():
            try:
                new_screenshots_dir(self.email_scr, 'trying_login_email')
                self.email_scr.login()
            except EmailAccountNotFound:
                pass
            except EmailAccountSuspended:
                # si tiene el email suspendido y no tiene confirmado el email, entonces
                # interrumpimos su creación
                if self.has_to_confirm_tw_email():
                    raise CancelCreation(self)
            except PageLoadError:
                raise CancelCreation(self)

            try:
                new_screenshots_dir(self.twitter_scr, 'trying_login_twitter')
                self.twitter_scr.login()
            except (TwitterBotDontExistsOnTwitterException,
                    TwitterEmailNotConfirmed):
                pass

        def signup_email():
            try:
                self.check_if_can_be_registered_on_hotmail()
                new_screenshots_dir(self.email_scr, 'signup_email')

                self.email_scr.sign_up()

                self.email_registered_ok = True
                self.date = utc_now()
                self.save()
                self.email_scr.take_screenshot('signed_up_sucessfully', force_take=True)
                self.email_scr.delay.seconds(7)
                self.email_scr.logger.info('%s signed up ok' % self.email)
            except (BotHasToWaitToRegister,
                    HotmailAccountNotCreated):
                raise SignupEmailError

        def confirm_tw_email():
            try:
                new_screenshots_dir(self.email_scr, 'confirm_tw_email')

                self.email_scr.confirm_tw_email()

                self.twitter_confirmed_email_ok = True
                self.save()
                self.email_scr.delay.seconds(8)
                settings.LOGGER.info('Confirmed twitter email %s for user %s' % (self.email, self.username))
                self.email_scr.take_screenshot('tw_email_confirmed_sucessfully', force_take=True)
            except ConfirmTwEmailError:
                settings.LOGGER.info('Login again on twitter.com..')
                try:
                    new_screenshots_dir(self.twitter_scr, 'login_twitter_again')
                    self.twitter_scr.login()
                except TwitterEmailNotConfirmed:
                    self.email_scr.delay.seconds(10)

                if self.has_to_confirm_tw_email():
                    new_screenshots_dir(self.email_scr, 'confirm_tw_email_after_resend')
                    try:
                        self.email_scr.confirm_tw_email()
                        self.twitter_confirmed_email_ok = True
                        self.save()
                        settings.LOGGER.info('Confirmed twitter email %s for user %s after resending confirmation' % (self.email, self.username))
                    except (TwitterEmailNotFound, PageLoadError) as e:
                        raise ConfirmTwEmailError
            except (EmailAccountNotFound,
                    TwitterEmailNotFound):
                raise ConfirmTwEmailError
            except Exception as ex:
                settings.LOGGER.exception('Error on bot %s confirming email %s' %
                                          (self.username, self.email))
                self.email_scr.take_screenshot('tw_email_confirmation_failure', force_take=True)
                raise ex

        try:
            if self.has_to_complete_creation():
                dir_index = [0]
                self.is_being_created = True
                self.save()

                t1 = utc_now()
                settings.LOGGER.info('Completing creation for bot %s (%s) behind proxy %s' %
                                     (self.username, self.real_name, self.proxy_for_usage.__unicode__()))

                # eliminamos el directorio de capturas previas para el usuario
                rmdir_if_exists(os.path.join(settings.SCREENSHOTS_DIR, '%s - %s' % (self.real_name, self.username)))

                # init scrappers
                self.email_scr = self.get_email_scrapper()
                self.email_scr.open_browser()
                self.twitter_scr = TwitterScrapper(self)
                self.twitter_scr.open_browser()

                self.twitter_scr.check_proxy_works_ok()

                # trying login email & twitter para verificar en cada cuenta si está correcta correctamente registrado o no
                if not first_time:
                    login_email_and_twitter()

                # signup email
                if self.has_to_register_email():
                    signup_email()

                # signup_twitter
                if self.has_to_register_twitter():
                    self.check_if_can_be_registered_on_twitter()
                    new_screenshots_dir(self.twitter_scr, 'signup_twitter')
                    self.twitter_scr.sign_up()

                # confirm_tw_email
                if self.has_to_confirm_tw_email():
                    try:
                        confirm_tw_email()
                    except EmailAccountNotFound:
                        raise CancelCreation

                # profile_completion
                if self.has_to_complete_tw_profile():
                    new_screenshots_dir(self.twitter_scr, 'tw_profile_completion')
                    self.twitter_scr.set_profile()

                t2 = utc_now()
                diff_secs = (t2 - t1).seconds
                if self.has_to_complete_creation():
                    settings.LOGGER.info('Bot "%s" processed incompletely in %s seconds' % (self.username, diff_secs))
                else:
                    settings.LOGGER.info('Bot "%s" completed sucessfully in %s seconds' % (self.username, diff_secs))
            else:
                settings.LOGGER.info('Bot %s is already completed' % self.user.username)
        except (PageLoadError,
                CancelCreation,
                SignupEmailError,
                SignupTwitterError,
                ConfirmTwEmailError,
                TwitterProfileCreationError):
            pass
        except Exception as ex:
            settings.LOGGER.exception('Error completing creation for bot %s' % self.username)
            raise ex
        finally:
            # cerramos las instancias abiertas
            try:
                if hasattr(self, 'email_scr'):
                    self.email_scr.close_browser()
                if hasattr(self, 'twitter_scr'):
                    self.twitter_scr.close_browser()
                self.is_being_created = False
                self.save()
            except Exception as ex:
                settings.LOGGER.exception('Error closing browsers instances for bot %s' % self.username)
                raise ex

    def generate_email(self):
        self.email = generate_random_username(self.real_name) + '@' + settings.EMAIL_ACCOUNT_TYPE

    def log_reason_to_not_complete_creation(self):
        if not self.has_to_complete_creation():
            settings.LOGGER.info('Bot %s is completed' % self.username)
        elif self.proxy_for_usage.is_unavailable_for_registration:
            settings.LOGGER.info('Bot %s has proxy %s unavailable for registration' %
                                 (self.username, self.proxy_for_usage.__unicode__()))
        elif self.proxy_for_usage.is_unavailable_for_registration:
            settings.LOGGER.info('Bot %s has proxy %s unavailable for usage' %
                                 (self.username, self.proxy_for_usage.__unicode__()))
        elif self.proxy_for_usage.is_phone_required:
            settings.LOGGER.info('Bot %s has proxy %s phone required' %
                                 (self.username, self.proxy_for_usage.__unicode__()))
        elif not self.get_group().reuse_proxies_with_suspended_bots:
            settings.LOGGER.info('Bot %s has proxiesgroup %s with reuse_proxies_with_suspended_bots=False' %
                                 (self.username. self.get_group().__unicode__()))

    def populate(self, from_bots_txts=False):
        try:
            settings.LOGGER.debug('Populating bot %d..' % self.pk)
            self.gender = random.randint(0, 1)
            gender_str = 'female' if self.gender == 1 else 'male'
            self.real_name = names.get_full_name(gender=gender_str)
            if not from_bots_txts:
                self.generate_email()
                self.username = generate_random_username(self.real_name)
                self.password_email = generate_random_string()
                self.password_twitter = generate_random_string(only_lowercase=True)
            self.birth_date = random_date(settings.BIRTH_INTERVAL[0], settings.BIRTH_INTERVAL[1])
            self.user_agent = generate_random_desktop_user_agent()
            self.random_offsets = settings.RANDOM_OFFSETS_ON_EL_CLICK
            if from_bots_txts:
                from project.models import ProxiesGroup
                proxies_group, already_exists = ProxiesGroup.objects.get_or_create(name='bots_from_txts')
                proxy, already_exists = Proxy.objects.get_or_create(
                    proxy='1.1.1.1:9999',
                    is_in_proxies_txts=False,
                    proxies_group=proxies_group
                )
                self.proxy_for_usage = proxy
            else:
                self.assign_proxy()
            self.save()
            settings.LOGGER.debug('Bot %s populated with proxy %s' %
                                 (self.username, self.proxy_for_usage.__unicode__()))
        except Exception as ex:
            settings.LOGGER.exception('Error populating bot')
            raise ex

    def set_tw_profile(self):
        """Se completa avatar y bio en su perfil de twitter"""
        self.scrapper.open_browser()
        self.scrapper.set_profile()
        self.scrapper.close_browser()

    def login_twitter_with_webdriver(self):
        """Esto lo único que hace es escribir en disco la cookie de twitter para el bot tras
        este haberse logueado"""
        scr = self.scrapper
        try:
            scr.logger.info('Login %s..' % self.username)
            scr.set_screenshots_dir('loggin_in_%s' % utc_now_to_str())
            scr.open_browser()
            scr.login()
            scr.delay.seconds(5)
            scr.logger.info('%s logged in ok' % self.username)
        except TwitterEmailNotConfirmed as e:
            self.clear_all_not_sent_ok_tweets()
            raise e
        finally:
            self.is_being_used = False
            self.save()
            scr.close_browser()

    def is_logged_on_twitter(self):
        """Nos dice si el bot está logueado en twitter, es decir, si existe el archivo para sus cookies"""
        return os.path.exists(self.get_cookies_filepath())

    def remove_cookies(self):
        """Eliminamos los archivos donde guardamos las cookies, por lo cual se da el bot como deslogueado"""
        rmfile_if_exists(self.get_cookies_file_for_casperjs())
        rmfile_if_exists(self.get_cookies_filepath())

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

    def can_tweet(self):
        """Nos dice si el bot puede tuitear"""

        # no podrá tuitear si está siendo usado
        if self.is_being_used:
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

        settings.LOGGER.debug('Bot %s getting item to send..' % self.username)
        # saco un item de los feeds disponibles para el grupo del bot
        # si ese item ya lo mandó el bot sacamos otro
        items_not_sent = self.get_feed_items_not_sent_yet()

        if not items_not_sent.exists():
            # Si no hay item se consultan todos los feeds hasta que se cree uno nuevo
            self.save_new_item_from_feeds()
            items_not_sent = self.get_feed_items_not_sent_yet()

        # volvemos a comprobar para ver si se añadió nuevo item desde feed
        if items_not_sent.exists():
            return items_not_sent.order_by('?').first()
        else:
            # en caso de enviarse todos los feeditems y no poder obtener nuevos de los feeds actuales,
            # entonces ordenamos de menor a mayor numero de tweets que se enviaron para cada uno.
            # si la cuenta es la misma ordenamos por date_created (así evitamos problemas si date_sent=None)
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

        feeditems_sent_by_bot = FeedItem.objects.filter(tweets__bot_used=self, tweets__sent_ok=True)\
            .values_list('pk', flat=True).distinct()

        # devolvemos todos los feeds en BD para el bot excluyendo los ya enviados en algún tweet
        return FeedItem.objects.filter(
            feed__feeds_groups__proxies_groups=proxies_group_for_bot,
        ).exclude(pk__in=feeditems_sent_by_bot)

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
        if tweets_sent.exists():
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

    def clear_all_not_sent_ok_tweets(self):
        """Elimina todos los tweets todavía no enviamos por el bot (ftweets, mctweets, mutweets..)"""

        from project.models import Tweet

        pending_to_send = Tweet.objects.filter(bot_used=self, sent_ok=False)
        count = pending_to_send.count()
        pending_to_send.delete()

        settings.LOGGER.warning('Deleted all tweets pending to send by bot %s (%i)..' % (self.username, count))

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

    def verify_mctweet_if_received_ok(self, mctweet):
        """Comprueba si le llegó ok la mención del tweet dado por parámetro"""

        def do_reply():
            def check_replied_ok():
                # comprobamos si se envió bien la respuesta
                try:
                    mention_received_ok_el.find_element_by_css_selector('ol.expanded-conversation')
                except NoSuchElementException:
                    raise FailureReplyingMcTweet(scr, mctweet)

            mention_received_ok_el = get_mention_received_ok_el()
            reply_btn = mention_received_ok_el.find_element_by_css_selector('.js-actionReply')
            scr.click(reply_btn)

            input_text = mention_received_ok_el.find_element_by_css_selector('#tweet-box-template')
            reply_msg = scr.get_random_reply()
            scr.fill_input_text(input_text, reply_msg)

            tweet_btn = mention_received_ok_el.find_element_by_css_selector('.tweet-button .btn')
            scr.click(tweet_btn)
            scr.delay.seconds(5)
            check_replied_ok()
            msg = 'Bot %s replied ok "%s" to mention from %s' % (mentioned_bot.username, reply_msg, mctweet.bot_used.username)
            settings.LOGGER.info(msg)
            scr.take_screenshot('mention_replied_ok', force_take=True)
            return msg

        def get_mention_received_ok_el():
            mention_received_ok_el = None
            mentions_timeline_el = scr.get_css_elements('#stream-items-id > li')
            for mention_el in mentions_timeline_el:
                # buscamos en la lista el último tweet enviado por ese bot
                user_mentioning = mention_el.find_element_by_css_selector('.username.js-action-profile-name').text.strip('@').lower()
                user_mentioning_is_bot = TwitterBot.objects.filter(username=user_mentioning).exists()

                if user_mentioning_is_bot and user_mentioning == mctweet.bot_used.username.lower():
                    # una vez que encontramos el último tweet enviado por ese bot vemos si coincide con el
                    # tweet que dice nuestra BD que se le mandó, sin contar con el link
                    mention_text = mention_el.find_element_by_css_selector('.js-tweet-text').text.strip()
                    mctweet_text = mctweet.compose(with_link=False)

                    # hacemos comprobación también por si están mal escritas las eñes, acentos, etc
                    if mctweet_text in mention_text \
                            or mctweet_text.encode('ascii', 'ignore') in mention_text.encode('ascii', 'ignore'):
                        mention_received_ok_el = mention_el
                        break

            return mention_received_ok_el

        from project.models import TweetCheckingMention

        try:
            if not mctweet.mentioned_bots.exists():
                raise Exception('You can\'t check mention over tweet %i without bot mentions' % mctweet.pk)
            else:
                tcm = TweetCheckingMention.objects.get(tweet=mctweet)
                scr = None
                # esto contendrá la cajita de la mención recibida
                try:
                    # nos logueamos con el bot destino y comprobamos
                    mentioned_bot = mctweet.mentioned_bots.first()
                    settings.LOGGER.info('Bot %s verifying tweet sent from %s..' %
                                         (mentioned_bot.username, mctweet.bot_used.username))
                    scr = mentioned_bot.scrapper

                    scr.set_screenshots_dir('checking_mention_%s_from_%s' % (mctweet.pk, mctweet.bot_used.username))
                    scr.open_browser()
                    scr.login()
                    scr.click('li.notifications')
                    scr.click('a[href="/mentions"]')

                    if get_mention_received_ok_el():
                        scr.take_screenshot('mention_arrived_ok', force_take=True)
                        msg = 'Bot %s received mention ok from %s' % (mentioned_bot.username, mctweet.bot_used.username)
                        settings.LOGGER.info(msg)
                        tcm.mentioning_works = True
                        tcm.destination_bot_checked_mention = True
                        tcm.destination_bot_checked_mention_date = utc_now()
                        tcm.save()

                        try:
                            msg2 = do_reply()
                        except Exception as e:
                            msg2 = 'Error replying bot %s to %s.' % (mentioned_bot.username, mctweet.bot_used.username)
                            if not hasattr(e, 'msg'):
                                settings.LOGGER.exception(msg2)
                                scr.take_screenshot('error_replying', force_take=True)
                            else:
                                msg2 = msg2 + ' Reason: ' + e.msg

                        return msg + '\n' + msg2
                    else:
                        msg = 'Bot %s not received mention from %s tweeting: %s' \
                              % (mentioned_bot.username, mctweet.bot_used.username, mctweet.compose())
                        scr.take_screenshot('mention_not_arrived', force_take=True)
                        settings.LOGGER.error(msg)
                        tcm.mentioning_works = False
                        tcm.destination_bot_checked_mention = True
                        tcm.destination_bot_checked_mention_date = utc_now()
                        tcm.save()
                        return msg

                except TwitterEmailNotConfirmed as e:
                    e.msg = 'Verifier %s has to confirm email first. Deleting mctweet %d sent from %s' \
                            % (mentioned_bot.username, mctweet.pk, mctweet.bot_used.username)
                    settings.LOGGER.debug(e.msg)
                    mctweet.delete()
                    raise e
                except Exception as e:
                    scr.take_screenshot('error_verifying', force_take=True)
                    raise e
                finally:
                    scr.close_browser()

                    try:
                        tcm = TweetCheckingMention.objects.get(tweet=mctweet)
                        tcm.destination_bot_is_checking_mention = False
                        tcm.save()
                    except TweetCheckingMention.DoesNotExist:
                        pass
        except Exception as e:
            msg = 'Error on bot %s verifying mctweet %d sent from %s.' \
                  % (mentioned_bot.username, mctweet.pk, mctweet.bot_used.username)
            if not hasattr(e, 'msg'):
                settings.LOGGER.exception(msg)
            else:
                msg = msg + ' Reason: ' + e.msg
            return msg
        finally:
            connection.close()

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

    def get_cookies_filename(self):
        return '%i_%s.txt' % (self.id, '_'.join(self.real_name.split(' ')))

    def get_cookies_filepath(self):
        return os.path.join(settings.PHANTOMJS_COOKIES_DIR, self.get_cookies_filename())

    def get_cookies_file_for_casperjs(self):
        return '%s.casperjs' % self.get_cookies_filepath()

    def set_cookies_files_for_casperjs(self):
        """Se loguea con webdriver y luego cada vez que queramos tomar el archivo de cookies para casperjs
        lo que hacemos es copiar el base generado con el webdriver ya que con casperjs lo modifica y siempre
        nos vuelve a pedir login"""
        cookies_filepath = self.get_cookies_filepath()
        casperjs_cookies_filepath = self.get_cookies_file_for_casperjs()
        if os.path.exists(cookies_filepath):

            # si existen cookies para casperjs anteriores las eliminamos y metemos las nuevas
            if os.path.exists(casperjs_cookies_filepath):
                os.remove(casperjs_cookies_filepath)

            copyfile(cookies_filepath, casperjs_cookies_filepath)

    def get_screenshots_dir(self):
        return os.path.join(settings.SCREENSHOTS_DIR, self.real_name + ' - ' + self.username)

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
                    tb_following = None
                    try:
                        tb_following = twitteruser.tb_followings.get(bot=self)
                    except TwitterBotFollowing.MultipleObjectsReturned:
                        # si tenemos varios registros de tbf entonces eliminamos los demás
                        settings.LOGGER.warning('Multiple tb_following entries for same bot %s, others will be erased'
                                                % self.username)
                        tb_followings = twitteruser.tb_followings.filter(bot=self)
                        for i, tbf in enumerate(tb_followings):
                            if i == 0:
                                tb_following = tbf
                            else:
                                tbf.delete()

                    tb_following.performed_follow = True
                    tb_following.followed_ok = True
                    if not tb_following.date_followed:
                        tb_following.date_followed = utc_now()
                    tb_following.save()

                    scr.delay.seconds(5)

                    scr.take_screenshot('%s_followed_ok' % twitteruser.username)
                    scr.logger.debug('%s followed ok' % twitteruser.username)
            except Exception as e:
                scr.take_screenshot('error_following_user_%s' % twitteruser.username, force_take=True)
                scr.logger.exception('Error following user %s' % twitteruser.username)
                raise e

        scr = self.scrapper
        scr.set_screenshots_dir('following_people_%s' % utc_now_to_str())

        try:
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
                        # nos aseguramos que el twitteruser no esté siendo seguido por otro bot
                        if twitteruser.tb_followings.count() > 1:
                            scr.logger.warning('%s is already being followed by another bot')
                            twitteruser.tb_followings.filter(bot=self).delete()
                        else:
                            follow_twitteruser(twitteruser)
                    msg = 'Bot %s followed %d twitterusers ok' % (self.username, twusers_to_follow.count())
                else:
                    msg = '%s not have to follow anyone for now. current ratio: %.1f, max ratio: %.1f' \
                          % (self.username, ratio, self.following_ratio)
                self.date_last_following = utc_now()
                self.save()
                settings.LOGGER.info(msg)
                return msg
            except (LoginTwitterError, PageLoadError) as e:
                scr.take_screenshot('following_people_error')
                raise e
            finally:
                scr.close_browser()
                self.is_being_used = False
                self.save()
                connection.close()
        except Exception as e:
            msg = 'Error on bot %s following twitterusers.' % self.username
            if not hasattr(e, 'msg'):
                settings.LOGGER.exception(msg)
            else:
                msg = msg + ' Reason: ' + e.msg

            return msg

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
            Q(is_suspended=True)
            # Q(num_suspensions_lifted__gt=0)
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

    def get_proxies_under_same_subnet(self):
        proxy_subnet = self.get_subnet_24()
        return self.__class__.objects.filter(proxy__istartswith=proxy_subnet)

    def get_bots_registered_under_same_subnet(self):
        same_subn_proxies = self.get_proxies_under_same_subnet()
        return TwitterBot.objects.filter(proxy_for_registration__in=same_subn_proxies)

    def get_bots_registered_under_same_subnet_since_days(self, days):
        """Saca los bots que fueron registrados hace x dias"""
        return self.get_bots_registered_under_same_subnet().filter(date__gte=utc_now() - datetime.timedelta(days=days))

    def can_register_bots_on_hotmail(self):
        """Nos dice si el proxy puede registrar bots en hotmail, ya que establecemos unos dias ventana entre registro y registro
        sobre misma subnet"""
        days_window = self.proxies_group.min_days_between_registrations_per_proxy_under_same_subnet
        # si no hay ningun bot registrado en hotmail en esos dias bajo la misma subnet, entonces podra registrar nuevos bots
        return not self\
            .get_bots_registered_under_same_subnet_since_days(days_window)\
            .filter(email_registered_ok=True)\
            .exists()

    def can_register_bots_on_twitter(self):
        """Nos dice si el proxy puede registrar bots en twitter, ya que establecemos unos dias ventana entre registro y registro
        sobre misma subnet"""
        days_window = self.proxies_group.min_days_between_registrations_per_proxy_under_same_subnet
        # si no hay ningun bot registrado en hotmail en esos dias bajo la misma subnet, entonces podra registrar nuevos bots
        return not self\
            .get_bots_registered_under_same_subnet_since_days(days_window)\
            .filter(twitter_registered_ok=True)\
            .exists()

    def get_days_left_to_allow_registrations(self):
        latest_bot = self.get_bots_registered_under_same_subnet().latest('date')
        days_window = self.proxies_group.min_days_between_registrations_per_proxy_under_same_subnet
        raise NotImplementedError

    def get_active_bots_using(self):
        """Devuelve los bots activos que están usando el proxy"""
        return self.twitter_bots_using.twitteable_regardless_of_proxy()

    def clear_pending_tweets_queue(self):
        """Elimina todos los tweets a la cola que hayan para todos los robots con este proxy"""
        from project.models import Tweet

        tweets_to_remove = Tweet.objects.filter(bot_used__proxy_for_usage=self).pending_to_send()
        count = tweets_to_remove.count()
        tweets_to_remove.delete()
        if count > 0:
            settings.LOGGER.info('Removed %i pending to send tweets from previously created in another group for proxy %s'
                                 %(count, self.__unicode__()))