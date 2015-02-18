# -*- coding: utf-8 -*-

import time
from core.managers import mutex
import twitter_bots.settings as settings
from utils import utc_now


class TwitterEmailNotFound(Exception):
    def __init__(self, scrapper):
        scrapper.take_screenshot('twitter_email_not_found_failure')
        scrapper.logger.warning('Twitter email not found')


class NotNewTwitterEmailFound(Exception):
    def __init__(self, scrapper):
        scrapper.take_screenshot('no_new_twitter_email_found_failure')
        scrapper.logger.warning('No new twitter email found')


class TwitterEmailNotConfirmed(Exception):
    def __init__(self, scrapper):
        scrapper.user.twitter_confirmed_email_ok = False
        scrapper.user.save()
        scrapper.logger.warning('Twitter email not confirmed yet')


class ErrorOpeningTwitterConfirmationLink(Exception):
    pass


class HotmailAccountNotCreated(Exception):
    def __init__(self, scrapper):
        scrapper.logger.error('Hotmail account can not be created')
        scrapper.take_screenshot('failure_registering_hotmail', force_take=True)


class EmailExistsOnTwitter(Exception):
    """Se lanza cuando intentamos registrarnos en twitter y sale que ya hay un usuario registrado con ese email"""
    def __init__(self, email):
        from core.models import TwitterBot
        settings.LOGGER.error('Email %s exists on twitter' % email)
        bot = TwitterBot.objects.get(email=email)
        bot.email_registered_ok = False
        bot.generate_email()
        bot.save()


class NotInEmailInbox(Exception):
    """Se lanza cuando esperamos estar en la bandeja de entrada del email del bot pero no es así"""
    def __init__(self, scrapper):
        scrapper.logger.error('Not in email inbox')
        scrapper.take_screenshot('not_in_email_inbox')


class TwitterAccountSuspended(Exception):
    def __init__(self, bot):
        bot.mark_as_suspended()
        settings.LOGGER.warning('Twitter account suspended for bot %s behind proxy %s'
                              % (bot.username, bot.proxy_for_usage.__unicode__()))


class TargetUserWasSuspended(Exception):
    def __init__(self, target_user):
        target_user.is_suspended = True
        target_user.save()
        settings.LOGGER.info('Target user %s was suspended' % target_user.username)


class TwitterAccountSuspendedAfterTryingUnsuspend(Exception):
    def __init__(self, scrapper):
        scrapper.logger.error('Twitter account still suspended after trying lifting suspension')


class TwitterAccountDead(Exception):
    def __init__(self, scrapper):
        scrapper.user.is_dead = True
        scrapper.user.date_death = utc_now()
        scrapper.user.save()
        scrapper.logger.warning('Exceeded 5 attemps to lift suspension. Twitter account dead :(')


class EmailAccountSuspended(Exception):
    def __init__(self, scrapper):
        scrapper.user.is_suspended_email = True
        scrapper.user.save()
        scrapper.logger.warning('Email account suspended')


class BotDetectedAsSpammerException(Exception):
    def __init__(self, scrapper):
        scrapper.user.is_suspended = False
        scrapper.user.save()
        scrapper.logger.warning('Twitter has detected this bot as spammer')


class FailureSendingTweetException(Exception):
    def __init__(self, scrapper, msg):
        settings.LOGGER.warning(msg)
        scrapper.take_screenshot('failure_sending_tweet', force_take=True)


class FailureReplyingMcTweet(Exception):
    def __init__(self, scrapper, mctweet):
        receiver = mctweet.mentioned_bots.first()
        sender = mctweet.bot_used
        settings.LOGGER.warning('Bot %s can\'t reply mctweet %d sent by %s' %
                                (receiver.username, mctweet.pk, sender.username))
        scrapper.take_screenshot('failure_replying_mctweet', force_take=True)


class TweetAlreadySent(Exception):
    def __init__(self, scrapper, tweet, msg):
        settings.LOGGER.warning(msg)
        tweet.sent_ok = True
        tweet.sending = False
        if not tweet.date_sent:
            tweet.date_sent = tweet.date_created
        tweet.save()

        scrapper.take_screenshot('tweet_already_sent', force_take=True)

class BotMustVerifyPhone(Exception):
    def __init__(self, scrapper):
        scrapper.user.proxy_for_usage.is_phone_required = True
        scrapper.user.proxy_for_usage.date_phone_required = utc_now()
        scrapper.user.proxy_for_usage.save()
        scrapper.logger.warning('Bot must do mobile phone verification')


class RequestAttemptsExceededException(Exception):
    def __init__(self, scrapper, url):
        scrapper.logger.warning('Exceeded attemps connecting to url %s' % url)


class TwitterBotDontExistsOnTwitterException(Exception):
    def __init__(self, scrapper):
        scrapper.user.mark_as_not_twitter_registered_ok()
        scrapper.logger.warning('Username %s dont exists on twitter' % scrapper.user.username)


class ConnectionError(Exception):
    pass


class ProxyConnectionError(ConnectionError):
    """Cuando no se puede conectar al proxy"""
    def __init__(self, bot):
        settings.LOGGER.error('Bot %s can\'t connect to proxy: %s' % (bot.username, bot.proxy_for_usage.__unicode__()))


class InternetConnectionError(ConnectionError):
    """Cuando, aun sin usar proxy, no se puede conectar a Internet"""
    def __init__(self):
        settings.LOGGER.error('Error connecting to Internet')
        time.sleep(100)


class ProxyTimeoutError(Exception):
    """Cuando se puede conectar al proxy pero no responde la página que pedimos"""
    def __init__(self, scrapper):

        scrapper.logger.error('Timeout error using proxy %s to request url %s, maybe you are using '
                              'unauthorized IP to connect. Page load timeout: %i secs' %
                              (scrapper.user.proxy_for_usage.__unicode__(),
                               scrapper.browser.current_url, settings.PAGE_LOAD_TIMEOUT))

        scrapper.take_screenshot('proxy_timeout_error', force_take=True)

        if hasattr(scrapper, 'email_scrapper'):
            scrapper.email_scrapper.close_browser()
        else:
            scrapper.close_browser()

        time.sleep(5)


class ProxyUrlRequestError(Exception):
    def __init__(self, scrapper, url):
        scrapper.logger.error('Proxy %s gets google.com ok, but couldn\'t get %s' % (scrapper.user.proxy_for_usage.__unicode__(), url))
        time.sleep(5)


class BlankPageError(Exception):
    def __init__(self, scrapper, url):
        scrapper.logger.error('Blank page source taken from url %s' % url)
        time.sleep(5)


class ProxyAccessDeniedError(Exception):
    def __init__(self, scrapper, url):
        scrapper.logger.error('Access denied to proxy %s requesting url %s' % (scrapper.user.proxy_for_usage.__unicode__(), url))
        scrapper.user.proxy_for_usage.mark_as_unavailable_for_use()
        time.sleep(5)


class ProfileStillNotCompleted(Exception):
    def __init__(self, scrapper):
        scrapper.logger.warning('Profile still not completed')


class IncompatibleUserAgent(Exception):
    def __init__(self, scrapper):
        scrapper.logger.warning('Incompatible user agent')
        scrapper.change_user_agent()


class EmailAccountNotFound(Exception):
    def __init__(self, scrapper):
        # scrapper.user.email_registered_ok = False
        # scrapper.user.save()
        scrapper.take_screenshot('email_account_doesnt_exists')
        scrapper.logger.warning('email account %s doesnt exists' % scrapper.user.email)
        scrapper.close_browser()


class PageNotReadyState(Exception):
    def __init__(self, scrapper):
        scrapper.take_screenshot('page_not_readystate')
        scrapper.logger.error('Exceeded %i secs waiting for DOM readystate after loading %s for bot %s under proxy %s' %
                                (settings.PAGE_READYSTATE_TIMEOUT, scrapper.browser.current_url, scrapper.user.username,
                                scrapper.user.proxy_for_usage.__unicode__()))


class NoElementToClick(Exception):
    def __init__(self, scrapper, el_str):
        scrapper.take_screenshot('click_error__%s' % el_str, force_take=True)
        scrapper.logger.error('no element %s present on %s, so can\'t be clicked' %
                              (el_str, scrapper.browser.current_url))
