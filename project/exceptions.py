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


class NoBotsFoundForSendingMentions(Exception):
    """Esto se lanza cuando la hebra no detecta más bots para poder lanzar menciones, bien por estar usándose en otra
    hebra o por tener que esperar algún periodo ventana"""

    def __init__(self):
        settings.LOGGER.warning('No bots found for sending mentions. All are already in use or waiting time windows.')


class NoTweetsOnMentionQueue(Exception):
    def __init__(self, bot=None):
        for_bot_msg = '' if not bot else ' to send by bot %s' % bot.username
        settings.LOGGER.warning('%s No tweets on mention queue%s.' % (get_thread_name(), for_bot_msg))


class NoMoreAvailableProxiesForRegistration(Exception):
    def __init__(self):
        from project.models import ProxiesGroup
        from core.models import Proxy

        settings.LOGGER.error('No available proxies for creating new bots. Sleeping %d seconds..' %
                              settings.TIME_SLEEPING_FOR_RESPAWN_BOT_CREATOR)
        ProxiesGroup.objects.log_groups_with_creation_enabled_disabled()
        Proxy.objects.log_proxies_valid_for_assign_group()
        time.sleep(settings.TIME_SLEEPING_FOR_RESPAWN_BOT_CREATOR)


class NoAvailableProxiesToAssignBotsForUse(Exception):
    def __init__(self, bot):
        """Vemos la razón por la que el bot no tiene proxy para poderselos asignar"""
        bot_group = bot.get_group()
        if not bot_group.is_bot_usage_enabled:
            settings.LOGGER.warning('Bot %s\'s group "%s" has bot usage disabled' %
                                    (bot.username, bot_group.__unicode__()))
        if bot.was_suspended() and not bot_group.reuse_proxies_with_suspended_bots:
            settings.LOGGER.warning('Suspended bot %s\'s group "%s" has reuse_proxies_with_suspended_bots disabled' %
                                    (bot.username, bot_group.__unicode__()))
        if bot_group.is_full_of_bots_using():
            settings.LOGGER.warning('Bot %s\'s group "%s" is full of bots assigned to each of their proxies (%d per proxy)' %
                                    (bot.username, bot_group.__unicode__(), bot_group.max_tw_bots_per_proxy_for_usage))
        settings.LOGGER.error('No more available proxies for use bot %s' % bot.username)

        # limpiamos de la cola todos los tweets que tuviera que mandar ese bot y todos los mctweets que
        # tuviera que verificar
        from project.models import Tweet
        Tweet.objects.clean_not_sent_ok(bot_used=bot)


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


class McTweetMustBeSent(Exception):
    def __init__(self, mc_tweet):
        self.mc_tweet = mc_tweet


class McTweetMustBeVerified(Exception):
    def __init__(self, mctweet):
        self.mctweet = mctweet


class CantRetrieveMoreItemsFromFeeds(Exception):
    def __init__(self, bot):
        settings.LOGGER.error('Bot %s can\'t retrieve new items from his feeds. All were already sent! You need '
                              'to add more feeds for his group "%s"' %
                              (bot.username, bot.get_group().__unicode__()))


class TweetConstructionError(Exception):
    def __init__(self, tweet):
        tweet.delete()


class TweetWithoutRecipientsError(TweetConstructionError):
    def __init__(self, tweet):
        super(TweetWithoutRecipientsError, self).__init__(tweet)
        settings.LOGGER.warning('Tweet without recipients will be deleted: %s' % tweet.compose())


class BotIsAlreadyBeingUsed(Exception):
    def __init__(self, bot):
        settings.LOGGER.debug('Bot %s is already being used' % bot.username)


class BotHasReachedConsecutiveTUMentions(Exception):
    def __init__(self, bot):
        self.bot = bot


class VerificationTimeWindowNotPassed(Exception):
    """
    Salta cuando no pasó el tiempo suficiente desde que el bot origen lanza el tweet y el destino
    todavía tiene que esperar un tiempo ventana antes de verificar
    """

    def __init__(self, mctweet):
        mctweet_sender = mctweet.bot_used
        mctweet_receiver = mctweet.mentioned_bots.first()
        sender_time_window = mctweet_sender.get_group().destination_bot_checking_time_window
        settings.LOGGER.debug(
            'Destination bot %s can\'t verify mctweet %d sent by %s. He has to wait more time (between %s minutes) '
            'since was sent (at %s)'
            %
            (
                mctweet_receiver.username,
                mctweet.pk,
                mctweet_sender.username,
                sender_time_window,
                mctweet.date_sent
            )
        )


class BotCantSendMctweet(Exception):
    pass


class BotHasNotEnoughTimePassedToTweetAgain(Exception):
    def __init__(self, bot):
        settings.LOGGER.debug('Bot %s has not enough time passed (between %s minutes) since '
                              'his last tweet sent (at %s)' %
                              (bot.username,
                               bot.get_group().time_between_tweets,
                               bot.get_last_tweet_sent().date_sent))


class MuTweetHasNotSentFTweetsEnough(Exception):
    def __init__(self, mutweet):
        self.mutweet = mutweet
        settings.LOGGER.debug('Mutweet %d has not sent ftweets enough (%d/%d)' %
                              (mutweet.pk,
                               mutweet.tweets_from_feed.count(),
                               mutweet.get_ftweets_count_to_send_before()))


class FTweetMustBeSent(Exception):
    def __init__(self, ftweet):
        self.ftweet = ftweet


class DestinationBotIsBeingUsed(Exception):
    def __init__(self, mctweet):
        destination_bot = mctweet.mentioned_bots.first()
        settings.LOGGER.debug('Bot %s can\'t verify mctweet from %s because %s is already '
                              'being used now' %
                              (destination_bot.username, mctweet.bot_used.username, destination_bot.username))


class LastMctweetFailedTimeWindowNotPassed(Exception):
    def __init__(self, bot):
        settings.LOGGER.debug('Bot %s not passed %s minutes after last mctweet failed (at %s)' % (
            bot.username,
            bot.get_group().mention_fail_time_window,
            bot.get_mctweets_verified().last().destination_bot_checked_mention_date))


class MethodOnlyAppliesToTuMentions(Exception):
    def __init__(self):
        settings.LOGGER.exception('This method only applies to twitteruser mentions')


class MethodOnlyAppliesToTbMentions(Exception):
    def __init__(self):
        settings.LOGGER.exception('This method only applies to twitterbot mentions')