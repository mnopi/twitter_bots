# -*- coding: utf-8 -*-
import datetime
import simplejson

from core.scrapper.utils import get_thread_name, has_elapsed_secs_since_time_ago, \
    generate_random_secs_from_minute_interval, utc_now, check_internet_connection_works, datetime_to_str
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


class NoRunningProjects(Exception):
    def __init__(self):
        settings.LOGGER.error('There are no running projects!. Sleeping..')
        time.sleep(20)


class ProjectFullOfUnmentionedTwitterusers(Exception):
    def __init__(self, project, valid_langs, unmentioned_count):
        # si hay algún mensaje en inglés entonces cualquier lang es válido
        langs_msg = ' with valid langs: %s' % ', '.join(project.get_langs_using()) \
            if valid_langs and not 'en' in valid_langs else ''

        settings.LOGGER.info('Project %s is full of unmentioned twitterusers%s (has: %d, max: %d)' %
                             (project.name, langs_msg, unmentioned_count, project.get_max_unmentioned_twitterusers()))
        settings.LOGGER.info('Sleeping %i seconds..' % 60)
        time.sleep(60)

class ExtractorReachedMaxConsecutivePagesRetrievedPerTUser(Exception):
    def __init__(self, extractor):
        settings.LOGGER.debug('Extractor %s reached max consecutive pages retrieved per target user (%i)' %
                             (extractor.twitter_bot.username, settings.MAX_CONSECUTIVE_PAGES_RETRIEVED_PER_TARGET_USER_EXTRACTION))


class ProjectHasAllHashtagsExtracted(Exception):
    def __init__(self, project):
        settings.LOGGER.warning('Project %s has no active hashtags now' % project.name)


class TwitteableBotsNotFound(Exception):
    def __init__(self):
        settings.LOGGER.warning('%s Bots not found to mention any user' % get_thread_name())
        time.sleep(10)


class NoAvailableBots(Exception):
    """Esto se lanza cuando la hebra no detecta más bots para poder usarse, bien por estar usándose en otra
    hebra o por tener que esperar algún periodo ventana"""

    def __init__(self):
        settings.LOGGER.warning('No available bots found. All already in use or waiting time windows.')


class NoAvailableBot(Exception):
    def __init__(self, bot, reason=None):
        if bot.is_being_used:
            reason = 'Is being used'
        elif not bot.tweets.pending_to_send().exists():
            reason = 'Has tweet to send queue empty'
        else:
            reason = 'Unknown'
        settings.LOGGER.warning('Bot %s not available now. Reason: %s' % (bot.username, reason))


class EmptyMentionQueue(Exception):
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
        base_msg = 'No more available proxies for use bot %s.' % bot.username

        if not bot_group.is_bot_usage_enabled:
            self.msg = 'Bot %s\'s group "%s" has bot usage disabled' \
                       % (bot.username, bot_group.__unicode__())
        if bot.was_suspended() and not bot_group.reuse_proxies_with_suspended_bots:
            self.msg = 'Suspended bot %s\'s group "%s" has reuse_proxies_with_suspended_bots disabled' \
                       % (bot.username, bot_group.__unicode__())
        if bot_group.is_full_of_bots_using():
            self.msg = 'Bot %s\'s group "%s" is full of bots assigned to each of their proxies (%d per proxy)' \
                       % (bot.username, bot_group.__unicode__(), bot_group.max_tw_bots_per_proxy_for_usage)

        settings.LOGGER.warning(self.msg)
        settings.LOGGER.error(base_msg)
        self.msg = base_msg + ' ' + self.msg

        # limpiamos de la cola todos los tweets que tuviera que mandar ese bot y todos los mctweets que
        # tuviera que verificar
        from project.models import Tweet
        Tweet.objects.clean_not_sent_ok(bot_used=bot)


class FatalError(Exception):
    def __init__(self, e):
        settings.LOGGER.exception('FATAL ERROR')
        time.sleep(10)


class TweetCreationException(Exception):
    pass


class ProjectWithoutUnmentionedTwitterusers(TweetCreationException):
    def __init__(self, project):
        settings.LOGGER.warning('Project %s has no more unmentioned users and will be stopped' %  project.name)
        project.is_running = False
        project.save()


class BotWithoutBotsToMention(TweetCreationException):
    def __init__(self, bot):
        self.msg = 'Bot %s has not bots to mention (group: %s)' % (bot.username, bot.get_group().__unicode__())
        settings.LOGGER.error(self.msg)


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


class TweetConstructionError(Exception):
    def __init__(self, tweet):
        self.msg = 'Tweet %d is wrong constructed and will be deleted' % tweet.pk
        settings.LOGGER.warning(self.msg)
        tweet.delete()


class BotIsAlreadyBeingUsed(Exception):
    def __init__(self, bot):
        self.msg = 'Bot %s is already being used' % bot.username
        settings.LOGGER.debug(self.msg)


class BotHasReachedConsecutiveTUMentions(Exception):
    def __init__(self, bot):
        self.bot = bot


class ProjectRunningWithoutBots(Exception):
    def __init__(self, project):
        settings.LOGGER.error('Project "%s" is marked as running and has no twitteable bots!' % project.name)


class VerificationTimeWindowNotPassed(Exception):
    """
    Salta cuando no pasó el tiempo suficiente desde que el bot origen lanza el tweet y el destino
    todavía tiene que esperar un tiempo ventana antes de verificar
    """

    def __init__(self, mctweet):
        mctweet_sender = mctweet.bot_used
        mctweet_receiver = mctweet.mentioned_bots.first()
        sender_time_window = mctweet_sender.get_group().destination_bot_checking_time_window
        self.msg = 'Destination bot %s can\'t verify mctweet %d sent by %s. He has to wait more time ' \
                   '(between %s minutes) since was sent (at %s)' %\
                   (mctweet_receiver.username,
                    mctweet.pk,
                    mctweet_sender.username,
                    sender_time_window,
                    mctweet.date_sent)
        settings.LOGGER.debug(self.msg)


class BotCantSendMctweet(Exception):
    pass


class BotHasNotEnoughTimePassedToTweetAgain(Exception):
    def __init__(self, bot):
        self.msg = 'Bot %s has not enough time passed (between %s minutes) since his last tweet ' \
                   'sent (at %s)' \
                   % (bot.username,
                      bot.get_group().time_between_tweets,
                      bot.get_last_tweet_sent().date_sent)
        settings.LOGGER.debug(self.msg)


class MuTweetHasNotSentFTweetsEnough(Exception):
    def __init__(self, mutweet):
        self.mutweet = mutweet
        self.msg = 'Bot %s has not sent ftweets enough (%d/%d) to tweet mutweet %d' \
                   % (mutweet.bot_used.username,
                      mutweet.tweets_from_feed.filter(tweet__sent_ok=True).count(),
                      mutweet.get_ftweets_count_to_send_before(),
                      mutweet.pk)
        settings.LOGGER.debug(self.msg)


class FTweetMustBeSent(Exception):
    def __init__(self, ftweet):
        self.ftweet = ftweet


class DestinationBotIsBeingUsed(Exception):
    def __init__(self, mctweet):
        destination_bot = mctweet.mentioned_bots.first()
        self.msg = 'Bot %s can\'t verify mctweet from %s because is already being used now' \
                   % (destination_bot.username, mctweet.bot_used.username)
        settings.LOGGER.debug(self.msg)


class DestinationBotIsDead(Exception):
    def __init__(self, mctweet):
        destination_bot = mctweet.mentioned_bots.first()
        self.msg = 'Bot %s can\'t verify mctweet %i because is dead. This mctweet will be deleted' \
                   % (destination_bot.username, mctweet.pk)
        settings.LOGGER.warning(self.msg)
        mctweet.delete()


class LastMctweetFailedTimeWindowNotPassed(Exception):
    def __init__(self, bot):
        self.msg = 'Bot %s not passed %s minutes after last mctweet failed (at %s)' \
                   % (bot.username,
                     bot.get_group().mention_fail_time_window,
                     bot.get_mctweets_verified().last().tweet_checking_mention.destination_bot_checked_mention_date)
        settings.LOGGER.debug(self.msg)


class MethodOnlyAppliesToTuMentions(Exception):
    def __init__(self):
        settings.LOGGER.exception('This method only applies to twitteruser mentions')


class MethodOnlyAppliesToTbMentions(Exception):
    def __init__(self):
        settings.LOGGER.exception('This method only applies to twitterbot mentions')


class SentOkMcTweetWithoutDateSent(Exception):
    def __init__(self, mctweet):
        self.msg = 'Sent ok mctweet %d without date sent! setting to utc_now..' % mctweet.pk
        settings.LOGGER.warning(self.msg)
        mctweet.date_sent = utc_now()
        mctweet.save()


class SenderBotHasToFollowPeople(Exception):
    def __init__(self, sender_bot):
        self.sender_bot = sender_bot
        self.msg = 'Sender bot %s has to follow people' % sender_bot.__unicode__()
        settings.LOGGER.info(self.msg)


class BotHasToWaitToRegister(Exception):
    def __init__(self, bot, where):
        settings.LOGGER.warning('Bot %s has to wait more days to be registered on %s' % (bot.username, where))


class CancelCreation(Exception):
    def __init__(self, bot):
        settings.LOGGER.warning('Bot %s has to cancel creation' % bot.username)


class ProjectHasAllTargetusersExtracted(Exception):
    def __init__(self, project):
        settings.LOGGER.warning('Project "%s" has all targetusers extracted' % project.name)


class ProjectHasNoTargetUsers(Exception):
    def __init__(self, project):
        settings.LOGGER.warning('Project "%s" has no target users added' % project.name)


class ProjectHasNoHashtags(Exception):
    def __init__(self, project):
        settings.LOGGER.warning('Project "%s" has no hashtags added' % project.name)


class NoAvaiableExtractors(Exception):
    def __init__(self, mode):
        settings.LOGGER.error('No available extractors for mode "%s". Sleeping..' % mode)
        time.sleep(30)


class HashtagOlderTweetDateLimitReached(Exception):
    def __init__(self, hashtag, oldest_tweet_date):
        """Reseteamos el hashtag si se alcanzó el límite de minutes ago para extraer"""
        oldest_limit = utc_now() - datetime.timedelta(seconds=settings.FIRST_HASHTAG_ROUND_MAX_MINUTES_AGO_FOR_OLDER_TWEET *60)\
            if hashtag.is_in_first_round()\
            else hashtag.current_round_oldest_tweet_limit

        settings.LOGGER.info('%sTweet older date limit reached for tweets '
                             '(oldest tweet on page: %s, oldest limit: %s)' %
                             (hashtag.pre_msg_for_logs(), datetime_to_str(oldest_tweet_date), datetime_to_str(oldest_limit)))

        hashtag.go_to_next_round()

class HashtagMaxUsersCountReached(Exception):
    def __init__(self, hashtag):
        settings.LOGGER.info('%sMax user count reached for tweets' % hashtag.pre_msg_for_logs())
        hashtag.go_to_next_round()


class TargetUserExtractionCompleted(Exception):
    def __init__(self, targetuser):
        settings.LOGGER.info('Extraction completed for target user %s' % targetuser.username)
        targetuser.mark_as_extracted()


class ProjectHasNoTwitterusersToExtract(Exception):
    def __init__(self, project):
        settings.LOGGER.error('Project %s has no sources for extracting twitterusers '
                              '(has no targetusers or hashtags available for extracting now, maybe '
                              'waiting timewindows or marked as is_active=False by admin)' % project.name)
        # project.is_running = False
        # project.save()


class ProjectHasNoMsgLinkOrPagelink(Exception):
    def __init__(self, project):
        settings.LOGGER.error('Project %s must have at least one msg+link or pagelink. It will we stopped' % project.name)
        project.is_running = False
        project.save()


class HashtagReachedConsecutivePagesWithoutEnoughNewTwitterusers(Exception):
    def __init__(self, hashtag):
        settings.LOGGER.warning('%sReached consecutive pages without enough twitterusers. '
                                'Has to wait a few minutes before continuing extractions' %
                                hashtag.pre_msg_for_logs())
        hashtag.go_to_next_round()
        hashtag.num_consecutive_pages_without_enough_new_twitterusers = 0
        hashtag.has_to_wait_timewindow_because_of_not_enough_new_twitterusers = True
        hashtag.save()


class HashtagExtractionWithoutResults(Exception):
    def __init__(self, hashtag):
        settings.LOGGER.error('No results for hashtag %s extraction. maybe max_id tweet was removed in twitter' %
                                hashtag.__unicode__())
        if hashtag.is_in_first_round():
            hashtag.max_id = None
            hashtag.save()
        else:
            hashtag.go_to_next_round()


class ProjectWithoutBotsToSendMentions(Exception):
    pass