# -*- coding: utf-8 -*-
from django.db.models import get_model
import feedparser
from django.contrib.auth.models import AbstractUser
from django.db import models
from scrapper.accounts.hotmail import HotmailScrapper
from core.querysets import ProxyQuerySet
from scrapper.exceptions import TwitterEmailNotFound
from scrapper.logger import get_browser_instance_id
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
        """Al bot se le asigna un proxy disponible según tenga cuentas ya creadas o no"""
        if self.has_no_accounts():
            self.proxy = Proxy.objects.available_for_registration().order_by('?')[0]
        else:
            self.proxy = Proxy.objects.available_for_usage().order_by('?')[0]
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
            settings.LOGGER.info('Completing creation for bot %s behind proxy %s @ %s' %
                                 (self.username, self.proxy.proxy, self.proxy.proxy_provider))

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
                    settings.LOGGER.info('%s %s signed up ok' % (get_browser_instance_id(self), self.email))

                # 2_signup_twitter
                if self.has_to_register_twitter():
                    self.twitter_scr.set_screenshots_dir('2_signup_twitter')
                    self.twitter_scr.sign_up()

                # 3_confirm_tw_email
                if self.has_to_confirm_tw_email():
                    self.email_scr.set_screenshots_dir('3_confirm_tw_email')
                    try:
                        self.email_scr.confirm_tw_email()
                    except TwitterEmailNotFound:
                        self.twitter_scr.set_screenshots_dir('resend_conf_email')
                        self.twitter_scr.login()
                    except Exception as ex:
                        settings.LOGGER.exception('Error on bot %s confirming email %s' %
                                                  (self.username, self.email))
                        self.email_scr.take_screenshot('tw_email_confirmation_failure', force_take=True)
                        raise ex
                    self.twitter_confirmed_email_ok = True
                    self.save()
                    self.email_scr.delay.seconds(8)
                    settings.LOGGER.info('Confirmed twitter email %s for user %s' % (self.email, self.username))
                    self.email_scr.take_screenshot('tw_email_confirmed_sucessfully', force_take=True)

                # 4_profile_completion
                if self.has_to_complete_tw_profile():
                    self.twitter_scr.set_screenshots_dir('4_tw_profile_completion')
                    self.twitter_scr.set_profile()

                # 5_lift_suspension
                if self.is_suspended:
                    self.twitter_scr.set_screenshots_dir('5_tw_lift_suspension')
                    self.twitter_scr.login()
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

            t2 = utc_now()
            diff_secs = (t2 - t1).seconds
            settings.LOGGER.info('Bot "%s" completed sucessfully in %s seconds' % (self.username, diff_secs))

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
            self.webdriver = settings.WEBDRIVER
            self.random_offsets = settings.RANDOM_OFFSETS_ON_EL_CLICK
            self.assign_proxy()
            self.save()
            settings.LOGGER.info('Bot %s populated with proxy %s @ %s' %
                                 (self.username, self.proxy.proxy, self.proxy.proxy_provider))
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
        return self.proxy_for_usage.proxies_group

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

    def make_mention_tweet_to_send(self, retry_counter=0):
        """Crea un tweet con mención pendiente de enviar"""
        from project.models import Tweet, TwitterUser

        # saco proyectos asignados para el robot que actualmente estén ejecutándose, ordenados de menor a mayor
        # número de tweets creados en la cola pendientes de enviar
        bot_projects = self.get_running_projects().order_by__queued_tweets()
        if bot_projects.exists():
            for project in bot_projects:
                unmentioned_for_tweet_to_send = TwitterUser.objects.get_unmentioned_on_project(
                    project,
                    limit=self.get_group().max_num_mentions_per_tweet
                )
                if unmentioned_for_tweet_to_send:
                    tweet_to_send = Tweet(
                        project=project,
                        tweet_msg=project.tweet_msgs.order_by('?')[0],
                        link=project.links.get(is_active=True),
                        bot_used=self,
                    )
                    tweet_to_send.save()

                    for unmentioned in unmentioned_for_tweet_to_send:
                        if tweet_to_send.length() + len(unmentioned.username) + 2 <= 140:
                            tweet_to_send.mentioned_users.add(unmentioned)
                        else:
                            break

                    settings.LOGGER.info('Queued (project: %s, bot: %s) >> %s' %
                                         (project.__unicode__(), self.__unicode__(), tweet_to_send.compose()))
                    break
                else:
                    settings.LOGGER.warning('Bot %s has not more users to mention for project %s' %
                                            (self.username, project.name))

        else:
            settings.LOGGER.warning('Bot %s has no running projects assigned at this moment' % self.__unicode__())



        #     for project in Project.objects.running().order_by__queued_tweets():
        #         # saco alguno que no fue mencionado por el bot
        #         unmentioned_by_bot = project.get_unmentioned_users()\
        #             .exclude(mentions__bot_used=self)
        #         if unmentioned_by_bot.exists():
        #             tweet_to_send = Tweet(
        #                 project=project,
        #                 tweet_msg=project.tweet_msgs.order_by('?')[0],
        #                 link=project.links.get(is_active=True),
        #                 bot_used=self,
        #             )
        #             tweet_to_send.save()
        #
        #             # añadimos usuarios a mencionar, los primeros en añadirse serán los últimos que hayan tuiteado
        #             try:
        #                 unmentioned_selected = unmentioned_by_bot.order_by('-last_tweet_date')[:settings.MAX_MENTIONS_PER_TWEET]
        #             except Exception as e:
        #                 unmentioned_selected = unmentioned_by_bot.all()
        #
        #             for unmentioned in unmentioned_selected:
        #                 if tweet_to_send.length() + len(unmentioned.username) + 2 <= 140:
        #                     tweet_to_send.mentioned_users.add(unmentioned)
        #                 else:
        #                     break
        #
        #             settings.LOGGER.info('Queued (project: %s, bot: %s) >> %s' %
        #                                  (project.__unicode__(), self.__unicode__(), tweet_to_send.compose()))
        #             break
        #         else:
        #             settings.LOGGER.warning('Bot %s has not more users to mention for project %s' %
        #                                     (self.username, project.name))
        # else:
        #     settings.LOGGER.info('Reached max queue size of %i tweets pending to send. Waiting %i seconds to retry (%i)..' %
        #                          (tweets_to_send_queue_length, settings.TIME_WAITING_FREE_QUEUE, retry_counter))
        #     time.sleep(settings.TIME_WAITING_FREE_QUEUE)
        #     self.make_mention_tweet_to_send(retry_counter=retry_counter + 1)

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

    # QUERYSET METHODS



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
        return '%s @ %s' % (self.proxy, self.proxy_provider)

    def get_bots_using(self):
        return self.__class__.objects.filter(twitter_bots_using__isnull=False)
