# -*- coding: utf-8 -*-
from django.contrib.auth.models import AbstractUser
from django.db import models
import pytz
from scrapper.exceptions import NoMoreAvaiableProxiesException
from scrapper.scrapper import Scrapper
from scrapper.accounts.twitter import TwitterScrapper
from core.managers import TwitterBotManager
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
    date_suspended_email = models.DateTimeField(null=True, blank=True)
    date_suspended_twitter = models.DateTimeField(null=True, blank=True)
    birth_date = models.DateTimeField(null=True, blank=True)

    GENDERS = {
        (0, 'male'),
        (1, 'female'),
    }
    gender = models.IntegerField(max_length=1, choices=GENDERS, default=0)

    it_works = models.BooleanField(default=False)
    is_manually_registered = models.BooleanField(default=False)
    has_fast_mode = models.BooleanField(default=False)
    user_agent = models.TextField(null=False, blank=True)
    proxy = models.CharField(max_length=21, null=False, blank=True)
    proxy_provider = models.CharField(max_length=50, null=False, blank=True)

    email_registered_ok = models.BooleanField(default=False)
    twitter_registered_ok = models.BooleanField(default=False)
    twitter_confirmed_email_ok = models.BooleanField(default=False)
    twitter_avatar_completed = models.BooleanField(default=False)
    twitter_bio_completed = models.BooleanField(default=False)
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
    must_verify_phone = models.BooleanField(default=False)

    objects = TwitterBotManager()

    def __unicode__(self):
        return self.username

    def __init__(self, *args, **kwargs):
        super(TwitterBot, self).__init__(*args, **kwargs)
        self.scrapper = TwitterScrapper(self)

    def is_valid(self):
        """Sólo se tomará el usuario como válido si no tiene cuenta suspendida y tiene el email confirmado"""
        return self.it_works and not self.has_to_be_completed()

    def has_no_accounts(self):
        return not self.email_registered_ok and not self.twitter_registered_ok

    def has_to_register_email(self):
        return settings.REGISTER_EMAIL and not self.email_registered_ok

    def has_to_register_twitter(self):
        return not self.twitter_registered_ok

    def has_to_confirm_tw_email(self):
        return settings.TW_CONFIRM_EMAIL and not self.twitter_confirmed_email_ok

    def has_to_complete_tw_profile(self):
        return not self.has_tw_profile_completed()

    def has_to_set_tw_avatar(self):
        return not self.twitter_avatar_completed and settings.TW_SET_AVATAR

    def has_to_set_tw_bio(self):
        return not self.twitter_bio_completed and settings.TW_SET_BIO

    def has_to_be_completed(self):
        return self.has_to_register_email() or \
               self.has_to_register_twitter() or \
               self.has_to_confirm_tw_email() or \
               self.has_to_complete_tw_profile()

    def has_tw_profile_completed(self):
        return not self.has_to_set_tw_avatar() and not self.has_to_set_tw_bio()

    def mark_as_suspended(self):
        self.it_works = False
        self.date_suspended = datetime.datetime.now()
        self.save()
        settings.LOGGER.warning('User %s has marked as suspended on twitter' % self.username)

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

    def assign_proxy(self, proxy=None, proxy_provider=None):
        """Le asigna un proxy disponible"""
        if settings.TOR_MODE:
            self.proxy = 'tor'
        elif proxy and proxy_provider:
            self.proxy = proxy
            self.proxy_provider = proxy_provider
            self.save()
        else:
            self.proxy, self.proxy_provider = random.choice(self.__class__.objects.get_available_proxies())
            self.save()

    def has_proxy_listed(self):
        "Mira si el proxy del usuario aparece en alguno de los .txt de la carpeta proxies"
        return self.__class__.objects.check_listed_proxy(self.proxy)

    def process(self):
        """Se procesa el bot una vez creado en BD. Esto sirve tanto para creación de bots como para
        comprobar que todavía funciona"""
        try:
            from core.managers import mutex
            try:
                mutex.acquire()
                if self.has_no_accounts():
                    self.populate()
                    self.assign_proxy()
                elif not self.proxy:
                    self.assign_proxy()
            finally:
                mutex.release()

            settings.LOGGER.info('Processing bot %s behind proxy %s' % (self.username, self.proxy))
            if self.has_to_be_completed():
                self.scrapper.scrape_bot_creation()
        finally:
            if self.has_no_accounts():
                settings.LOGGER.exception('Bot %s has any account and will be deleted' % self.username)
                self.delete()

    def generate_email(self):
        self.email = generate_random_username(self.real_name) + '@' + settings.EMAIL_ACCOUNT_TYPE

    def populate(self):
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
        self.webdriver = settings.WEBDRIVER
        self.random_offsets = settings.RANDOM_OFFSETS_ON_EL_CLICK
        self.save()

    def set_tw_profile(self):
        """Se completa avatar y bio en su perfil de twitter"""
        self.scrapper.login()
        self.scrapper.set_profile()
        self.delay.seconds(7)
        self.scrapper.close_browser()

    def confirm_tw_email(self):
        ts = TwitterScrapper(self)
        ts.set_email_scrapper()
        ts.email_scrapper.login()
        ts.email_scrapper.confirm_tw_email()

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

    def tweeting_time_interval_lapsed(self):
        "Mira si ha pasado el suficiente tiempo desde la ultima vez que tuiteo"
        bot_tweets = self.get_sent_ok_tweets().order_by('-date_sent')
        if bot_tweets:
            last_tweet = bot_tweets[0]
            now_utc = datetime.datetime.now().replace(tzinfo=pytz.utc)
            random_seconds = random.randint(60*settings.TIME_BETWEEN_TWEETS[0], 60*settings.TIME_BETWEEN_TWEETS[1])  # entre 2 y 7 minutos por tweet
            return (now_utc - last_tweet.date_sent).seconds >= random_seconds
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