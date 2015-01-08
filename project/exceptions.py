# -*- coding: utf-8 -*-

from core.scrapper.utils import get_thread_name, has_elapsed_secs_since_time_ago, \
    generate_random_secs_from_minute_interval
from twitter_bots import settings
import time

__author__ = 'Michel'


class RateLimitedException(Exception):
    def __init__(self, extractor):
        settings.LOGGER.warning('Rate limited exceeded for extractor %s' % extractor.twitter_bot.username)
        extractor.is_rate_limited = True
        extractor.save()


class AllFollowersExtracted(Exception):
    def __init__(self):
        settings.LOGGER.warning('All followers were extracted from all active target_users in all active projects')
        time.sleep(20)


class AllHashtagsExtracted(Exception):
    def __init__(self):
        settings.LOGGER.warning('All hashtags were extracted from all active hashtags in all active projects')
        time.sleep(20)


class TwitteableBotsNotFound(Exception):
    def __init__(self):
        settings.LOGGER.warning('%s Bots not found to mention any user' % get_thread_name())
        time.sleep(10)


class AllBotsInUse(Exception):
    """Esto se lanza cuando la hebra no detecta bots que puedan hacer nada, bien por estar usándose en otra
    hebra o por tener que esperar algún periodo ventana"""

    def __init__(self):
        settings.LOGGER.warning('All bots are already in use or waiting time windows.')


class NoTweetsOnQueue(Exception):
    def __init__(self, bot=None):
        for_bot_msg = '' if not bot else ' to send by bot %s' % bot.username
        settings.LOGGER.warning('%s No tweets on queue%s.' % (get_thread_name(), for_bot_msg))


class NoMoreAvailableProxiesForRegistration(Exception):
    def __init__(self):
        from project.models import ProxiesGroup
        from core.models import Proxy

        settings.LOGGER.error('No available proxies for creating new bots. Sleeping %d seconds..' %
                              settings.TIME_SLEEPING_FOR_RESPAWN_BOT_CREATOR)
        ProxiesGroup.objects.log_groups_with_creation_enabled_disabled()
        Proxy.objects.log_proxies_valid_for_assign_group()
        time.sleep(settings.TIME_SLEEPING_FOR_RESPAWN_BOT_CREATOR)


class BotHasNoProxiesForUsage(Exception):
    def __init__(self, bot):
        bot_group = bot.get_group()
        if not bot_group.is_bot_usage_enabled:
            settings.LOGGER.warning('Bot %s has assigned group "%s" with bot usage disabled' %
                                    (bot.username, bot_group.__unicode__()))
        else:
            settings.LOGGER.error('No more available proxies for use bot %s' % bot.username)


class SuspendedBotHasNoProxiesForUsage(Exception):
    def __init__(self, bot):
        bot_group = bot.get_group()
        if not bot_group.is_bot_usage_enabled:
            settings.LOGGER.warning('Bot %s has assigned group "%s" with bot usage disabled' %
                                    (bot.username, bot_group.__unicode__()))
        elif not bot_group.reuse_proxies_with_suspended_bots:
            settings.LOGGER.warning('Suspended bot %s has assigned group "%s" with reuse_proxies_with_suspended_bots disabled' %
                                    (bot.username, bot_group.__unicode__()))
        else:
            settings.LOGGER.error('No more available proxies for use bot %s' % bot.username)


class FatalError(Exception):
    def __init__(self, e):
        settings.LOGGER.exception('FATAL ERROR')
        time.sleep(10)


class TweetCreationException(Exception):
    def __init__(self, tweet):
        settings.LOGGER.warning('Error creating tweet %i and will be deleted' % tweet.pk)
        tweet.delete()


class BotHasToCheckIfMentioningWorks(Exception):
    """Al mirar en la cola si un tweet se puede enviar puede que se lanze esta excepción cuando se tenga que
    verificar si el bot que lo envía puede seguir mencionando a usuarios de twitter.
    """

    def __init__(self, mc_tweet):
        # le metemos el mc_tweet a la excepción para que luego fuera del mutex se envíe
        self.mc_tweet = mc_tweet


class BotHasToSendMcTweet(Exception):
    def __init__(self, mc_tweet):
        self.mc_tweet = mc_tweet


class DestinationBotHasToVerifyMcTweet(Exception):
    def __init__(self, mc_tweet):
        self.mc_tweet = mc_tweet


class CantRetrieveMoreItemsFromFeeds(Exception):
    def __init__(self, bot):
        settings.LOGGER.error('Bot %s can\'t retrieve new items from his feeds. All were already sent! You need '
                              'to add more feeds for his group "%s"' %
                              (bot.username, bot.get_group().__unicode__()))
