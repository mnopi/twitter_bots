# -*- coding: utf-8 -*-
import os

from django.contrib.auth.models import AbstractUser
from django.db import models
import pytz
from selenium.common.exceptions import TimeoutException
from scrapper import Scrapper
from scrapper.accounts.twitter import TwitterScrapper
from scrapper.managers import TwitterBotManager
from scrapper import settings

from twitter_bots.settings import LOGGER
from scrapper.utils import *
from scrapper import delay


class User(AbstractUser):
    pass


class TwitterBot(models.Model):
    real_name = models.CharField(max_length=50, null=False, blank=True)
    email = models.CharField(max_length=256, null=False, blank=True)
    password_twitter = models.CharField(max_length=20, null=False, blank=True)
    password_email = models.CharField(max_length=20, null=False, blank=True)
    username = models.CharField(max_length=50, null=False, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    date_suspended_email = models.DateTimeField(null=True, blank=True)
    date_suspended_twitter = models.DateTimeField(null=True, blank=True)
    birth_date = models.DateTimeField(null=True, blank=True)

    GENDERS = {
        (0, 'male'),
        (1, 'female'),
    }
    gender = models.IntegerField(max_length=1, choices=GENDERS, default=0)

    it_works = models.BooleanField(default=True)
    is_manually_registered = models.BooleanField(default=False)
    has_fast_mode = models.BooleanField(default=False)
    user_agent = models.TextField(null=False, blank=True)
    proxy = models.CharField(max_length=21, null=False, blank=True)
    proxy_provider = models.CharField(max_length=50, null=False, blank=True)

    email_registered_ok = models.BooleanField(default=False)
    twitter_registered_ok = models.BooleanField(default=False)
    twitter_confirmed_email_ok = models.BooleanField(default=False)
    cookies = models.TextField(null=True, blank=True)
    twitter_profile_completed = models.BooleanField(default=False)
    FIREFOX = 'FI'
    CHROME = 'CH'
    PHANTOMJS = 'PH'
    WEBDRIVERS = (
        ('FI', 'Firefox'),
        ('CH', 'Chrome'),
        ('PH', 'PhantomJS'),
    )
    webdriver = models.CharField(max_length=2, choices=WEBDRIVERS, default='FI')
    random_offsets = models.BooleanField(default=False)
    random_mouse_paths = models.BooleanField(default=False)

    objects = TwitterBotManager()

    def __unicode__(self):
        return self.username

    def is_valid(self):
        """Sólo se tomará el usuario como válido si no tiene cuenta suspendida y tiene el email confirmado"""
        return self.it_works and self.twitter_confirmed_email_ok

    def has_no_accounts(self):
        return not self.email_registered_ok and not self.twitter_registered_ok

    def has_to_register_email(self):
        return settings.REGISTER_EMAIL and not self.email_registered_ok

    def has_to_register_twitter(self):
        return not self.twitter_registered_ok

    def has_to_confirm_tw_email(self):
        return settings.TW_CONFIRM_EMAIL and not self.twitter_confirmed_email_ok

    def mark_as_suspended(self):
        self.it_works = False
        self.date_suspended = datetime.datetime.now()
        self.save()
        LOGGER.warning('User %s has marked as suspended on twitter' % self.username)

    def mark_as_not_twitter_registered_ok(self):
        self.twitter_registered_ok = False
        self.twitter_confirmed_email_ok = False
        self.save()
        LOGGER.warning('User %s has marked as not twitter registered ok' % self.username)

    def get_email_username(self):
        """Pilla el usuario de ese email (sin el @etc.com)"""
        return self.email.split('@')[0]

    def get_email_account_domain(self):
        """Pilla el dominio de ese email (por ejemplo @gmail.com)"""
        return self.email.split('@')[1]

    def assign_proxy(self, proxy=None, proxy_provider=None):
        """Busca un proxy disponible y se lo asigna"""
        def proxy_is_avaiable(proxy):
            """
            Para que un proxy esté disponible se tiene que cumplir:
                -   que el número de bots con ese proxy no superen el máximo por proxy
                -   que el último usuario que se registró usando ese proxy lo haya hecho
                    hace más de el periodo mínimo de días
            """
            if proxy:
                num_users_with_that_proxy = self.__class__.objects.filter(proxy=proxy).count()
                space_ok = num_users_with_that_proxy < settings.MAX_TWT_BOTS_PER_PROXY

                if space_ok:
                    if num_users_with_that_proxy > 0:
                        latest_user_with_that_proxy = self.__class__.objects.filter(proxy=proxy).latest('date')
                        diff_ok = (datetime.datetime.now().replace(tzinfo=pytz.utc)
                                   - latest_user_with_that_proxy.date).days >= 5
                        return diff_ok
                    else:
                        # si no hay ningún usuario usando el proxy evidentemente se da como disponible
                        return True
                else:
                    return False
            else:
                # si 'proxy' es una cadena vacía..
                return False

        if settings.TOR_MODE:
            self.proxy = 'tor'
        elif proxy and proxy_provider:
            self.proxy = proxy
            self.proxy_provider = proxy_provider
            self.save()
        else:
            found_avaiable_proxy = False
            proxies_folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'proxies')
            for (dirpath, dirnames, filenames) in os.walk(proxies_folder):
                if found_avaiable_proxy: break
                for filename in filenames:  # myprivateproxy.txt
                    if found_avaiable_proxy: break
                    with open(os.path.join(dirpath, filename)) as f:
                        proxies_lines = f.readlines()
                        for proxy in proxies_lines:
                            proxy = proxy.replace('\n', '')
                            proxy = proxy.replace(' ', '')
                            found_avaiable_proxy = proxy_is_avaiable(proxy)
                            if found_avaiable_proxy:
                                self.proxy = proxy
                                self.proxy_provider = filename.split('.')[0]
                                self.save()
                                break

            if not found_avaiable_proxy:
                raise Exception('There are not avaiable proxies to connect bot with username=%s, id=%i'
                                % (self.username, self.id))

    def perform_registrations(self):
        def automate_registrations():
            """Abre una ventana del navegador con varias pestañas y va haciendo todo"""
            try:
                if settings.FAST_MODE:
                    LOGGER.warning('Fast mode is enabled!')

                ts = TwitterScrapper(self)
                ts.open_browser()
                ts.signup_email_account()
                ts.sign_up()
                ts.confirm_user_email()
                ts.close_browser()
            except Exception as ex:
                LOGGER.exception('Automated registrations failed for "%s"' % self.username)
                raise ex

        def manual_registrations():
            """Abre las ventanas iniciales y espera a que estén todas cerradas para continuar
            con el registro del usuario en BD, entendiendo así que ya se hizo todo el registro, comprobar email, etc"""
            try:
                if self.has_no_accounts():
                    self.populate()

                scr = Scrapper(self)
                scr.open_browser()

                if self.has_to_register_email():
                    # ventana de email
                    if self.get_email_account_domain() == 'gmail.com':
                        scr.browser.get(settings.URLS['gmail_reg'])
                    elif self.get_email_account_domain() == 'hushmail.com':
                        scr.browser.get(settings.URLS['hushmail_reg'])
                    elif self.get_email_account_domain() == 'hotmail.com':
                        scr.browser.get(settings.URLS['hotmail_reg'])

                if self.has_to_register_twitter():
                    # ventana de twitter
                    scr.open_url_in_new_window(settings.URLS['twitter_reg'])

                while scr.browser.window_handles:
                    time.sleep(0.5)

                self.email_registered_ok = True
                self.twitter_registered_ok = True
                self.save()
            except Exception as ex:
                # si el proxy falla, etc
                LOGGER.exception('Manual registrations failed for "%s" and has been marked as reusable' % self.username)
                raise ex

        try:
            t1 = datetime.datetime.utcnow()
            if settings.MANUAL_MODE:
                self.is_manually_registered = True
                manual_registrations()
            else:
                automate_registrations()

            t2 = datetime.datetime.utcnow()
            diff_secs = (t2 - t1).seconds
            self.save()
            LOGGER.info('bot "%s" procesado en %s segundos' % (self.username, diff_secs))
            if self.has_to_register_email():
                LOGGER.warning('\t"%s": error al registrar email "%s"' % (self.username, self.email))
            if self.has_to_register_twitter():
                LOGGER.warning('\t"%s": error al registrar twitter' % self.username)
        except Exception as ex:
            LOGGER.exception('Error performing registration for bot id=%i, username=%s' % self.pk, self.username)
            raise ex

    def populate(self):
        if self.has_no_accounts():
            self.gender = random.randint(0, 1)

            gender_str = 'female' if self.gender == 1 else 'male'
            full_name = names.get_full_name(gender=gender_str)

            self.real_name = full_name
            self.email = generate_random_username(full_name) + '@' + settings.EMAIL_ACCOUNT_TYPE
            self.username = generate_random_username(full_name)
            self.password_email = generate_random_string()
            self.password_twitter = generate_random_string(only_lowercase=True)
            self.birth_date = random_date(settings.BIRTH_INTERVAL[0], settings.BIRTH_INTERVAL[1])
            self.user_agent = generate_random_desktop_user_agent()
            self.has_fast_mode = settings.FAST_MODE
            self.webdriver = settings.WEBDRIVER
            self.random_offsets = settings.RANDOM_OFFSETS_ON_EL_CLICK
            self.save()

    def set_tw_profile(self):
        """Se completa avatar y bio en su perfil de twitter"""
        ts = TwitterScrapper(self)
        ts.login()
        ts.set_profile()
        delay.seconds(7)
        ts.close_browser()
        self.twitter_profile_completed = True
        self.save()

    def check_proxy_avaiable(self):
        """Mira si su proxy está en las listas de proxies actuales, por si el usuario no se usó hace
        mucho tiempo y se refrescó la lista de proxies con los proveedores, ya que lo hacen cada mes normalmente"""
        if not settings.TOR_MODE:
            proxy_exists = False
            proxies_folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'proxies')
            for (dirpath, dirnames, filenames) in os.walk(proxies_folder):
                if proxy_exists: break
                for filename in filenames:  # myprivateproxy.txt
                    if proxy_exists: break
                    with open(os.path.join(dirpath, filename)) as f:
                        proxies_lines = f.readlines()
                        for proxy in proxies_lines:
                            proxy = proxy.replace('\n', '')
                            proxy = proxy.replace(' ', '')
                            if proxy == self.proxy:
                                proxy_exists = True
                                break

            if not proxy_exists:
                LOGGER.info('Proxy %s @ %s not avaiable for %s. Assigning another avaiable proxy..'
                            % (self.proxy, self.proxy_provider, self.username))
                self.assign_proxy()
                LOGGER.info('\t.. new proxy %s @ %s assigned ok' % (self.proxy, self.proxy_provider))
