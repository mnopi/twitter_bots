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
                                           scrapper.user.proxy_for_usage.__unicode__()))
        time.sleep(5)


class ProfileStillNotCompleted(Exception):
    def __init__(self, bot):
        settings.LOGGER.warning('Profile still not completed for bot %s' % bot.__unicode__())