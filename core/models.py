# -*- coding: utf-8 -*-
from django.db.models import Q
import feedparser
from django.contrib.auth.models import AbstractUser
from django.db import models
from project.exceptions import NoMoreAvailableProxiesForRegistration, BotHasNoProxiesForUsage, SuspendedBotHasNoProxiesForUsage, \
    TweetCreationException, BotHasToCheckIfMentioningWorks, CantRetrieveMoreItemsFromFeeds, BotHasToSendMcTweet, \
    DestinationBotHasToVerifyMcTweet
from core.scrapper.scrapper import Scrapper, INVALID_EMAIL_DOMAIN_MSG
from core.scrapper.accounts.hotmail import HotmailScrapper
from core.scrapper.accounts.twitter import TwitterScrapper
from core.scrapper.exceptions import TwitterEmailNotFound, \
    TwitterAccountDead, TwitterAccountSuspended, ProfileStillNotCompleted
from core.scrapper.utils import *
from core.managers import TwitterBotManager, ProxyManager, mutex
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

            settings.LOGGER.info('Assigned proxy for usage %s to bot %s' % (self.proxy_for_usage, self.username))

        if self.has_to_register_accounts():
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

                if self.has_to_register_email() or self.has_to_register_twitter() or self.has_to_confirm_tw_email():
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

    def is_being_used(self):
        if self.is_already_sending_tweet() or self.is_already_checking_mention():
            settings.LOGGER.debug('Bot %s is already being used' % self.username)
            return True
        else:
            return False

    def can_tweet(self):
        """Nos dice si el bot puede tuitear"""

        # no podrá tuitear si está siendo usado
        if self.is_being_used():
            return False

        # tampoco si no pasó el tiempo suficiente desde que envió el último tweet
        elif not self.has_enough_time_passed_since_his_last_tweet():
            return False

        else:
            return True

    def make_tweet_to_send(self, from_feeds=False, only_mention_bots=False):
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
                    if bot_group.has_link:
                        tweet_to_send.add_link(project)
                    if bot_group.has_tweet_img:
                        tweet_to_send.add_image(project)
                    if bot_group.has_page_announced:
                        tweet_to_send.add_page_announced(project)
                    if bot_group.has_mentions:
                        if only_mention_bots:
                            tweet_to_send.add_bots_to_mention()
                        else:
                            tweet_to_send.add_mentions()

                    # si mandamos un item de los feeds entonces quitamos tweet_msg y ponemos feed_msg
                    if from_feeds:
                        item_to_send = self.get_item_to_send()
                        tweet_to_send.feed_item = item_to_send
                        tweet_to_send.save()

                    # tras encontrar ese proyecto con el que hemos podido construir el tweet salimos para
                    # dar paso al siguiente bot
                    break
                except TweetCreationException:
                    continue
        else:
            settings.LOGGER.warning('Bot %s has no running projects assigned at this moment' % self.__unicode__())

    def get_item_to_send(self):
        "Crea un tweet a partir de algún feed pendiente de enviar"

        from project.models import Project, Tweet, TweetMsg, Link, Feed

        # saco un item de los feeds disponibles para el grupo del bot
        # si ese item ya lo mandó el bot sacamos otro
        items_not_sent = self.get_feed_items_not_sent_yet()
        if not items_not_sent.exists():
            # Si no hay item se consultan todos los feeds hasta que se cree uno nuevo
            self.save_new_item_from_feeds()
            items_not_sent = self.get_feed_items_not_sent_yet()

        # volvemos a comprobar para ver si se añadió nuevo item desde feed
        if not items_not_sent.exists():
            raise CantRetrieveMoreItemsFromFeeds(self)
        else:
            return items_not_sent.first()

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

    def get_last_tweet_mentioning_bots(self):
        """Saca el último tweet lanzado por el bot que menciona a otros bots"""

        ment_bots_tweets = self.tweets.sent_ok()\
            .filter(mentioned_bots__isnull=False)
        if ment_bots_tweets.exists():
            return ment_bots_tweets.latest('date_sent')
        else:
            return None

    def get_consecutive_tweets_mentioning_twitterusers(self):
        last_tweet_mentioning_bots = self.get_last_tweet_mentioning_bots()
        if last_tweet_mentioning_bots:
            return self.tweets.sent_ok().filter(date_sent__gt=last_tweet_mentioning_bots.date_sent)
        else:
            return self.tweets.sent_ok()

    def has_reached_consecutive_mentions_to_twitterusers(self):
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

    def get_or_create_mc_tweet(self):
        """El bot busca su tweet de verificación (mentioning check tweet). Si no existe crea uno"""

        from project.models import Tweet

        # vemos si hay algún tweet de verificación pendiente de comprobar
        mc_tweet_not_checked = Tweet.objects.mentioning_bots().by_bot(self).not_checked_if_mention_arrives_ok()
        if mc_tweet_not_checked.exists():
            if mc_tweet_not_checked.count() > 1:
                settings.LOGGER.warning('There were found multiple mentioning check tweets pending to send from '
                                      'bot %s and will be deleted' % self.username)
                self.clear_not_sent_ok_mc_tweets()
                self.make_tweet_to_send(from_feeds=True, only_mention_bots=True)
        else:
            # si no existe dicho tweet de verificación el bot lo crea
            self.make_tweet_to_send(from_feeds=True, only_mention_bots=True)

        return mc_tweet_not_checked.first()

    def get_rest_of_completed_bots_under_same_group(self):
        """Devuelve una lista con los bots completos bajo el mismo grupo del bot dado. Ordenados
        poniendo primero los que el bot tuiteó hace más tiempo"""
        bots = TwitterBot.objects\
            .using_proxies_group(self.get_group())\
            .completed()\
            .exclude(pk=self.pk)

        # sacamos bots ordenamos de más antiguo a más nuevo mencionado por el bot, los bots que aún no hayan sido
        # mencionados por el bot los ponemos al principio
        bots = list(bots)
        without_mention_received = []
        with_mention_received = []

        for b in bots:
            mentions_to_b = b.mentions.filter(bot_used=self)
            if mentions_to_b.exists():
                b.last_mention_received_by_bot_date = mentions_to_b.latest('date_sent').date_sent
                with_mention_received.append(b)
            else:
                without_mention_received.append(b)

        with_mention_received.sort(key=lambda b: b.last_mention_received_by_bot_date, reverse=False)
        return without_mention_received + with_mention_received

    def order_by__oldest_mentioned_by_bot(self, bot):
        """Ordena los bots de menor a mayor veces mencionado por el bot dado"""

        bots = list(self)
        for b in bots:
            b.last_mention_received_by_bot_date = b.mentions.filter(bot_used=bot).latest('date_sent')

        bots.sort(key=lambda x: x.last_mention_received_by_bot_date, reverse=False)

        pk_list = [b.pk for b in bots]

        return self.filter(pk__in=[b.pk for b in bots])

    def can_mention_twitterusers(self):
        """Nos dice si el bot puede mencionar usuarios de twitter"""

        def has_passed_mention_fail_time_window():
            """Nos dice si el bot ha superado el tiempo ventana para poder mencionar tras no funcionarle la mención"""

            mention_verification = last_tweet_mentioning_bots.tweet_checking_mention
            return has_elapsed_secs_since_time_ago(
                mention_verification.destination_bot_checked_mention_date,
                generate_random_secs_from_minute_interval(self.get_group().mention_fail_time_window)
            )

        def has_not_reached_consecutive_mentions_limit():
            # comprobamos si excedió el número consecutivo de menciones a usuarios de twitter
            if self.has_reached_consecutive_mentions_to_twitterusers():
                log_reason_to_not_send_mention('has reached consecutive mentions sent to twitterusers')
                try_to_send_mctweet()
            else:
                # si aún no superó el límite de menciones consecutivas entonces de momento
                # lo damos por que funciona. Esto es, si por ejemplo el límite es 3 y el bot
                # va por 2, entonces de momento no hay problema
                return True

        def log_reason_to_not_send_mention(reason):
            settings.LOGGER.debug('Bot %s can\'t mention twitter users because %s' % (self.username, reason))

        def try_to_verify_mctweet():
            """Se intenta verificar mctweet desde su bot destino.

            Si está ocupado enviando un tweet, verificando otro mctweet, o aún hay que esperar el periodo ventana
            para la verificación, entonces devolvemos false.

            De lo contrario, lanzamos excepción DestinationBotHasToVerifyMcTweet para que salga del mutex
            y se ponga a verificar.
            """

            from project.models import TweetCheckingMention

            # comprobamos que el bot destino no esté siendo usando
            destination_bot = mc_tweet.mentioned_bots.first()
            if not destination_bot.is_being_used():
                tcm = TweetCheckingMention.objects.get_or_create(tweet=mc_tweet)[0]

                destination_bot_checking_time_window = self.get_group().destination_bot_checking_time_window
                time_window_passed = has_elapsed_secs_since_time_ago(
                    mc_tweet.date_sent,
                    generate_random_secs_from_minute_interval(destination_bot_checking_time_window)
                )
                if time_window_passed:
                    tcm.destination_bot_is_checking_mention = True
                    tcm.save()
                    raise DestinationBotHasToVerifyMcTweet(mc_tweet)
                else:
                    settings.LOGGER.debug('Destination bot %s has to wait more time (between %s minutes) to verify '
                                          'mctweet sent at %s' %
                                          (destination_bot.username,
                                           destination_bot_checking_time_window,
                                           mc_tweet.date_sent))
                    return False
            else:
                settings.LOGGER.debug('Destination bot %s can\'t verify mctweet from %s because is being used' %
                                      (destination_bot.username, self.username))
                return False

        def try_to_send_mctweet():
            from project.models import TweetCheckingMention

            settings.LOGGER.debug('Bot %s trying to send mctweet..' % self.username)

            if self.can_tweet():
                mc_tweet = self.get_or_create_mc_tweet()
                mc_tweet.sending = True
                mc_tweet.save()
                raise BotHasToSendMcTweet(mc_tweet)

            # si el bot no está verificando mctweet en otra hebra buscamos un mctweet
            # pendiente de verificar por ese bot
            else:
                settings.LOGGER.debug('Bot %s trying to verify mctweet..' % self.username)

                if not self.is_already_checking_mention():
                    tcms_to_verify = TweetCheckingMention.objects.filter(
                        tweet__mentioned_bots=self,
                        destination_bot_checked_mention=False
                    )
                    if tcms_to_verify.exists():
                        raise DestinationBotHasToVerifyMcTweet(tcms_to_verify.first().tweet)
                    else:
                        settings.LOGGER.debug('Bot %s has no mctweets to verify' % self.username)


        # el mctweet es el último tweet que lanzó el bot mencionando otro bot
        last_tweet_mentioning_bots = self.get_last_tweet_mentioning_bots()
        mc_tweet = last_tweet_mentioning_bots

        # si ya existe su mctweet..
        if mc_tweet:
            try:
                # miramos el registro de verificación de ese tweet, si no existe lanzará excepción que
                # trataremos más abajo
                tcm = mc_tweet.tweet_checking_mention

                # si el bot destino está verificando otro mctweet entonces no podremos hacer nada
                if tcm.destination_bot_is_checking_mention:
                    log_reason_to_not_send_mention('destination bot is checking if mc_tweet arrived from him')
                    return False

                # si aún no se verificó el mctweet
                elif not tcm.destination_bot_checked_mention:
                    destination_bot = last_tweet_mentioning_bots.mentioned_bots.first()
                    log_reason_to_not_send_mention('his mc_tweet sent to %s has to be verified first' %
                                                   destination_bot.username)
                    return try_to_verify_mctweet()

                # si se verificó el mctweet, comprobamos que aún no alcanzamos el límite de menciones consecutivas
                # a usuarios de twitter
                elif tcm.mentioning_works:
                    return has_not_reached_consecutive_mentions_limit() and self.can_tweet()

                # si se superó el periodo ventana tras último mctweet fallido, volvemos a enviar otro mctweet
                elif has_passed_mention_fail_time_window():
                    log_reason_to_not_send_mention('destination bot has failed last mc_tweet verification')
                    try_to_send_mctweet()

                else:
                    settings.LOGGER.warning('Bot %s can\'t send mentions to twitter users. '
                                            'Last failed verification was at %s' %
                                            (self.username, tcm.destination_bot_checked_mention_date))
                    return False

            except ObjectDoesNotExist:
                # si no existe tcm es que falta verificar el mctweet
                return try_to_verify_mctweet()
        else:
            # si no existe mctweet comprobamos si se sobrepasaron las menciones consecutivas a usuarios de twitter
            # esto se hace sólo una vez por bot ya que evalúa el inicio, cuando aún no existe ningún mctweet
            # para él
            return has_not_reached_consecutive_mentions_limit() and self.can_tweet()

    def can_mention_bots(self):
        pass

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
                settings.LOGGER.debug('Bot %s has not enough time passed (between %s minutes) '
                                      'since his last tweet sent (at %s)' %
                                      (self.username, self.get_group().time_between_tweets, last_tweet_sent.date_sent))
                return False

    def check_if_tweet_received_ok(self, tweet):
        """Comprueba si le llegó ok la mención del tweet dado por parámetro"""

        from project.models import TweetCheckingMention

        if not tweet.mentioned_bots.exists():
            raise Exception('You can\'t check mention over tweet %i without bot mentions' % tweet.pk)
        else:
            tcm = TweetCheckingMention.objects.get(tweet=tweet)
            try:
                # nos logueamos con el bot destino y comprobamos
                mentioned_bot = tweet.mentioned_bots.all()[0]
                settings.LOGGER.info('Bot %s checking if mention from %s arrived ok..' %
                                     (mentioned_bot.username, tweet.bot_used.username))
                mentioned_bot.scrapper.set_screenshots_dir('checking_mention_%s_from_%s' % (tweet.pk, tweet.bot_used.username))
                mentioned_bot.scrapper.open_browser()
                mentioned_bot.scrapper.login()
                mentioned_bot.scrapper.click('li.notifications')
                mentioned_bot.scrapper.click('a[href="/mentions"]')
                mention_received_ok = False

                mentions_timeline_el = mentioned_bot.scrapper.get_css_elements('#stream-items-id > li')
                for mention_el in mentions_timeline_el:
                    # buscamos en la lista el último tweet enviado por ese bot
                    user_mentioning = mention_el.find_element_by_css_selector('.username.js-action-profile-name').text.strip('@')
                    user_mentioning_is_bot = TwitterBot.objects.filter(username=user_mentioning).exists()

                    if user_mentioning_is_bot:
                        if user_mentioning == tweet.bot_used.username:
                            # una vez que encontramos el último tweet enviado por ese bot vemos si coincide con el
                            # tweet que dice nuestra BD que se le mandó, sin contar con el link
                            mention_text = mention_el.find_element_by_css_selector('.js-tweet-text').text.strip()
                            mention_received_ok = tweet.compose(for_verif_mctweets=True) in mention_text
                            break
                        else:
                            continue

                if mention_received_ok:
                    tcm.mentioning_works = True
                    mentioned_bot.scrapper.take_screenshot('mention_arrived_ok')
                    settings.LOGGER.info('Bot %s received mention ok from %s' %
                                         (mentioned_bot.username, tweet.bot_used.username))
                else:
                    tcm.mentioning_works = False
                    mentioned_bot.scrapper.take_screenshot('mention_not_arrived')
                    settings.LOGGER.error('Bot %s not received mention from %s tweeting: %s' %
                                          (mentioned_bot.username, tweet.bot_used.username, tweet.compose()))

                tcm.destination_bot_checked_mention = True
                tcm.destination_bot_checked_mention_date = utc_now()
            finally:
                tcm.destination_bot_is_checking_mention = False
                tcm.save()

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