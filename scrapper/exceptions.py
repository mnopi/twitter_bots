# -*- coding: utf-8 -*-

import time
import twitter_bots.settings as settings
from utils import utc_now


class TwitterEmailNotFound(Exception):
    pass


class TwitterEmailNotConfirmed(Exception):
    def __init__(self, bot):
        bot.twitter_confirmed_email_ok = False
        bot.save()
        settings.LOGGER.warning('Bot %s hasnt confirmed twitter email %s yet' % (bot.username, bot.email))


class TwitterAccountSuspended(Exception):
    def __init__(self, bot):
        bot.mark_as_suspended()
        settings.LOGGER.warning('Bot %s has his twitter account suspended' % bot.username)


class TwitterAccountDead(Exception):
    def __init__(self, bot):
        bot.is_dead = True
        bot.date_death = utc_now()
        bot.save()
        settings.LOGGER.warning(':(:(:( Bot %s has his twitter account dead' % bot.username)


class EmailAccountSuspended(Exception):
    def __init__(self, bot):
        bot.is_suspended_email = True
        bot.save()
        settings.LOGGER.warning('Bot %s has his email account %s suspended' %
                                (bot.username, bot.email))


class BotDetectedAsSpammerException(Exception):
    def __init__(self, bot):
        bot.is_suspended = False
        bot.save()
        settings.LOGGER.warning('Bot %s was detected as spammer' % bot.username)


class FailureSendingTweetException(Exception):
    pass


class BotMustVerifyPhone(Exception):
    def __init__(self, bot):
        bot.proxy.is_phone_required = True
        bot.proxy.date_phone_required = utc_now()
        bot.proxy.save()
        settings.LOGGER.warning('Bot %s must do mobile phone verification' % bot.username)


class RequestAttemptsExceededException(Exception):
    def __init__(self, bot, url):
        settings.LOGGER.warning('Exceeded attemps connecting to %s from bot %s' % (url, bot.username))


class TwitterBotDontExistsOnTwitterException(Exception):
    def __init__(self, bot):
        bot.mark_as_not_twitter_registered_ok()
        settings.LOGGER.warning('Username %s dont exists on twitter' % bot.username)


class NoMoreAvailableProxiesForRegistration(Exception):
    def __init__(self):
        settings.LOGGER.error('There is no more avaiable proxies for creating new bots. Sleeping..')
        time.sleep(120)


class NoMoreAvailableProxiesForUsage(Exception):
    def __init__(self):
        settings.LOGGER.error('There is no more avaiable proxies for usage. Sleeping..')
        time.sleep(120)


class FatalError(Exception):
    def __init__(self):
        settings.LOGGER.exception('FATAL ERROR')
        time.sleep(10)


class ProxyConnectionError(Exception):
    """Cuando no se puede conectar al proxy"""
    def __init__(self, scrapper):
        settings.LOGGER.error('Error connecting to proxy %s' % scrapper.user.proxy.__unicode__())
        time.sleep(10)


class InternetConnectionError(Exception):
    """Cuando no se puede conectar al proxy"""
    def __init__(self):
        settings.LOGGER.error('Error connecting to Internet')
        time.sleep(100)


class ProxyTimeoutError(Exception):
    """Cuando se puede conectar al proxy pero no responde la página que pedimos"""
    def __init__(self, scrapper):

        settings.LOGGER.error('Timeout error on bot %s using proxy %s to request address %s, maybe you are using '
                              'unauthorized IP to connect. Page load timeout: %i secs' %
                              (scrapper.user.username, scrapper.user.proxy.__unicode__(),
                               scrapper.browser.current_url, settings.PAGE_LOAD_TIMEOUT))

        scrapper.take_screenshot('proxy_timeout_error', force_take=True)

        if hasattr(scrapper, 'email_scrapper'):
            scrapper.email_scrapper.close_browser()
        else:
            scrapper.close_browser()

        time.sleep(5)


class ProxyUrlRequestError(Exception):
    def __init__(self, scrapper, url):
        settings.LOGGER.error('%s Couldn\'t get %s url for user %s behind proxy %s' %
                                          (scrapper.browser_id, url, scrapper.user.username,
                                           scrapper.user.proxy.__unicode__()))
        time.sleep(5)