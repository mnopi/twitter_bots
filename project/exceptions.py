import threading
import datetime
from scrapper.utils import get_thread_name
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
    def __init__(self):
        settings.LOGGER.warning('%s All bots in use. Retrying in %i seconds' %
                                (get_thread_name(), settings.TIME_WAITING_AVAIABLE_BOT_TO_TWEET))
        time.sleep(settings.TIME_WAITING_AVAIABLE_BOT_TO_TWEET)


class NoTweetsOnQueue(Exception):
    def __init__(self):
        settings.LOGGER.warning('%s No tweets on queue. Retrying in %s seconds' %
                                (get_thread_name(), settings.TIME_WAITING_AVAIABLE_BOT_TO_TWEET))
        time.sleep(settings.TIME_WAITING_AVAIABLE_BOT_TO_TWEET)


class NoMoreAvailableProxiesForRegistration(Exception):
    def __init__(self):
        from project.models import ProxiesGroup
        from core.models import Proxy

        settings.LOGGER.error('No available proxies for creating new bots. Sleeping %d seconds..' %
                              settings.TIME_SLEEPING_FOR_RESPAWN_BOT_CREATOR)
        ProxiesGroup.objects.log_groups_with_creation_disabled()
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


class SuspendedBotWithoutProxy(Exception):
    def __init__(self, bot):
        settings.LOGGER.warning('Could not assign new proxy to bot %s because was suspended' % bot.username)


class FatalError(Exception):
    def __init__(self):
        settings.LOGGER.error('FATAL ERROR')
        time.sleep(10)


class TweetCreationException(Exception):
    def __init__(self, tweet):
        settings.LOGGER.warning('Error creating tweet %i and will be deleted' % tweet.pk)
        tweet.delete()
