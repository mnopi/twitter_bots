# -*- coding: utf-8 -*-

import time
import twitter_bots.settings as settings
from utils import utc_now


class TwitterEmailNotFound(Exception):
    pass


class TwitterEmailNotConfirmed(Exception):
    def __init__(self, scrapper):
        scrapper.user.twitter_confirmed_email_ok = False
        scrapper.user.save()
        scrapper.logger.warning('Twitter email not confirmed yet')


class TwitterAccountSuspended(Exception):
    def __init__(self, scrapper):
        scrapper.user.mark_as_suspended()
        scrapper.logger.warning('Twitter account suspended')


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
    pass


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
        scrapper.logger.warning('Username dont exists on twitter')


class ConnectionError(Exception):
    pass


class ProxyConnectionError(ConnectionError):
    """Cuando no se puede conectar al proxy"""
    def __init__(self, scrapper):
        scrapper.logger.error('Proxy %s not available for usage' % scrapper.user.proxy_for_usage.__unicode__())
        # scrapper.user.proxy_for_usage.mark_as_unavailable_for_use()
        time.sleep(10)


class InternetConnectionError(ConnectionError):
    """Cuando, aun sin usar proxy, no se puede conectar a Internet"""
    def __init__(self, scrapper):
        scrapper.logger.error('Error connecting to Internet')
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
        scrapper.take_screenshot('wrong_email_account')
        scrapper.logger.warning('Wrong email account')
        scrapper.close_browser()


class PageNotReadyState(Exception):
    def __init__(self, scrapper):
        scrapper.take_screenshot('page_not_readystate')
        scrapper.logger.error('Exceeded %i secs waiting for DOM readystate after loading %s' %
                                (settings.PAGE_READYSTATE_TIMEOUT, scrapper.browser.current_url))


class NoElementToClick(Exception):
    def __init__(self, scrapper, el_str):
        scrapper.take_screenshot('click_error__%s' % el_str, force_take=True)
        scrapper.logger.error('no element %s present on %s, so can\'t be clicked' %
                              (el_str, scrapper.browser.current_url))
