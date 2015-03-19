# -*- coding: utf-8 -*-

import time
from urllib2 import URLError
from core.managers import mutex
import twitter_bots.settings as settings
from utils import utc_now

#
# clases padre
#

class PageLoadError(Exception):
    pass


class ConnectionError(PageLoadError):
    pass


class TwitterEmailNotFound(Exception):
    """Esta excepción se lanza cuando no se encuenta en la bandeja de entrada el email de confirmación
    que tiene que enviar twitter después del registro"""
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
        self.msg = 'Twitter email not confirmed yet'
        scrapper.logger.warning(self.msg)


class AboutBlankPage(PageLoadError):
    def __init__(self, scrapper):
        self.msg = 'about:blank page error'
        scrapper.logger.error(self.msg)
        scrapper.take_screenshot('about_blank_error')


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
        self.msg = 'Twitter account suspended for bot %s behind proxy %s'\
                   % (bot.username, bot.proxy_for_usage.__unicode__())
        settings.LOGGER.warning(self.msg)


class TargetUserWasSuspended(Exception):
    def __init__(self, target_user):
        target_user.is_suspended = True
        target_user.save()
        settings.LOGGER.info('Target user %s was suspended' % target_user.username)


class TwitterAccountSuspendedAfterTryingUnsuspend(Exception):
    def __init__(self, scrapper):
        scrapper.logger.error('Twitter account still suspended after trying lifting suspension')


class TwitterAccountDead(Exception):
    def __init__(self, bot):
        from project.models import Tweet

        bot.is_dead = True
        bot.date_death = utc_now()
        bot.save()
        # eliminamos todos sus tweets de la cola
        Tweet.objects.filter(sent_ok=False, bot_used=bot).delete()
        self.msg = 'Twitter account %s dead :(' % bot.username
        settings.LOGGER.error(self.msg)


class EmailAccountSuspended(Exception):
    def __init__(self, scrapper):
        scrapper.user.is_suspended_email = True
        scrapper.user.date_suspended_email = utc_now()
        scrapper.user.save()
        self.msg = 'Email account suspended'
        scrapper.logger.warning(self.msg)


class BotDetectedAsSpammerException(Exception):
    def __init__(self, scrapper):
        scrapper.user.is_suspended = False
        scrapper.user.save()
        self.msg = 'Twitter has detected bot %s as spammer' % scrapper.user.username
        scrapper.logger.warning(self.msg)


class FailureSendingTweet(Exception):
    def __init__(self, tweet):
        self.msg = 'Error on bot %s sending tweet %s' \
                   % (tweet.bot_used.username, tweet.pk)
        settings.LOGGER.error(self.msg)


class BotNotLoggedIn(Exception):
    def __init__(self, bot):
        self.msg = 'Bot %s not logged in twitter' % bot.username
        settings.LOGGER.warning(self.msg)


class FailureReplyingMcTweet(Exception):
    def __init__(self, scrapper, mctweet):
        receiver = mctweet.mentioned_bots.first()
        sender = mctweet.bot_used
        self.msg = 'Bot %s can\'t reply mctweet %d sent by %s' \
                   % (receiver.username, mctweet.pk, sender.username)
        settings.LOGGER.warning(self.msg)
        scrapper.take_screenshot('failure_replying_mctweet', force_take=True)


class TweetAlreadySent(Exception):
    def __init__(self, tweet):
        self.msg = 'Tweet %d was already sent by bot %s' \
                   % (tweet.pk, tweet.bot_used.username)
        settings.LOGGER.warning(self.msg)
        tweet.sent_ok = True
        tweet.sending = False
        if not tweet.date_sent:
            tweet.date_sent = tweet.date_created
        tweet.save()


class UnknownErrorSendingTweet(Exception):
    def __init__(self, tweet):
        self.msg = 'Unknown error sending tweet %s by bot %s' % (tweet.pk, tweet.bot_used.username)
        settings.LOGGER.error(self.msg)


class CaptchaRequiredTweet(Exception):
    def __init__(self, tweet):
        self.msg = 'Captcha required tweet %i to send by bot %s' % (tweet.pk, tweet.bot_used.username)
        settings.LOGGER.error(self.msg)


class CaptchaIncorrect(Exception):
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
        scrapper.logger.warning('Username %s dont exists on twitter' % scrapper.user.username)


class ProxyConnectionError(ConnectionError):
    """Cuando no se puede conectar al proxy"""
    def __init__(self, bot):
        self.msg = 'Bot %s can\'t connect to proxy: %s' % (bot.username, bot.proxy_for_usage.__unicode__())
        settings.LOGGER.error(self.msg)


class InternetConnectionError(ConnectionError):
    """Cuando, aun sin usar proxy, no se puede conectar a Internet"""
    def __init__(self):
        self.msg = 'Error connecting to Internet'
        settings.LOGGER.error(self.msg)
        time.sleep(100)


class ProxyTimeoutError(ConnectionError):
    """Cuando se puede conectar al proxy pero no responde la página que pedimos"""
    def __init__(self, scrapper):
        self.msg = 'Timeout error using proxy %s to request url %s, maybe you are using ' \
                   'unauthorized IP to connect. Page load timeout: %i secs' \
                   % (scrapper.user.proxy_for_usage.__unicode__(),
                      scrapper.browser.current_url,
                      settings.WEBDRIVER_PAGE_LOAD_TIMEOUT)
        scrapper.logger.error(self.msg)

        scrapper.take_screenshot('proxy_timeout_error', force_take=True)

        if hasattr(scrapper, 'email_scrapper'):
            scrapper.email_scrapper.close_browser()
        else:
            scrapper.close_browser()

        time.sleep(5)


class ProxyUrlRequestError(ConnectionError):
    def __init__(self, scrapper, url):
        self.msg = 'Proxy %s gets google.com ok, but couldn\'t get %s' % (scrapper.user.proxy_for_usage.__unicode__(), url)
        scrapper.logger.error(self.msg)
        time.sleep(5)


class BlankPageError(PageLoadError):
    def __init__(self, scrapper, url):
        scrapper.take_screenshot('blank_page_source_failure')
        self.msg = 'Blank page source taken from url %s' % url
        scrapper.logger.error(self.msg)
        time.sleep(5)


class ProxyAccessDeniedError(ConnectionError):
    def __init__(self, scrapper, url):
        self.msg = 'Access denied to proxy %s requesting url %s' % (scrapper.user.proxy_for_usage.__unicode__(), url)
        scrapper.logger.error(self.msg)
        scrapper.user.proxy_for_usage.mark_as_unavailable_for_use()
        time.sleep(5)


class ProfileStillNotCompleted(Exception):
    def __init__(self, scrapper):
        scrapper.logger.warning('Profile still not completed')


class IncompatibleUserAgent(Exception):
    def __init__(self, scrapper):
        scrapper.logger.warning('Incompatible user agent: %s' % scrapper.user.user_agent)
        scrapper.change_user_agent()


class EmailAccountNotFound(Exception):
    def __init__(self, scrapper):
        if scrapper.user.email_registered_ok:
            scrapper.user.email_registered_ok = False
            scrapper.user.save()
        scrapper.take_screenshot('email_account_doesnt_exists')
        scrapper.logger.warning('email account %s doesnt exists' % scrapper.user.email)


class SignupEmailError(Exception):
    pass


class SignupTwitterError(Exception):
    pass


class LoginTwitterError(Exception):
    def __init__(self, bot):
        self.msg = 'Error on bot %s login on twitter' % bot.username
        settings.LOGGER.error(self.msg)


class FollowTwitterUsersError(Exception):
    def __init__(self, bot):
        self.msg = 'Error on bot %s following twitterusers' % bot.username
        settings.LOGGER.error(self.msg)


class ConfirmTwEmailError(Exception):
    pass


class TwitterProfileCreationError(Exception):
    pass


class PageNotRetrievedOkByWebdriver(PageLoadError):
    def __init__(self, scrapper):
        scrapper.take_screenshot('page_not_retrieved_ok')
        self.msg = 'page not retrieved ok by webdriver: %s' % scrapper.browser.current_url
        scrapper.logger.error(self.msg)
        scrapper.close_browser()


class PageNotReadyState(PageLoadError):
    def __init__(self, scrapper):
        try:
            scrapper.take_screenshot('page_not_readystate')
            self.msg = 'Exceeded %i secs waiting for DOM readystate after loading %s for bot %s under proxy %s' \
                       % (settings.WEBDRIVER_PAGE_READYSTATE_TIMEOUT, scrapper.browser.current_url, scrapper.user.username,
                        scrapper.user.proxy_for_usage.__unicode__())
            scrapper.logger.error(self.msg)
        except URLError as e:
            # scrapper.logger.error('URLError: cannot retrieve URL from scrapper. Proxy used: %s' %
            #                       scrapper.user.proxy_for_usage.__unicode__())
            raise e


class NoElementToClick(Exception):
    def __init__(self, scrapper, el_str):
        try:
            scrapper.take_screenshot('click_error__%s' % el_str, force_take=True)
            scrapper.logger.error('no element %s present on %s, so can\'t be clicked' %
                                  (el_str, scrapper.browser.current_url))
        except URLError as e:
            raise e


class ErrorDownloadingPicFromGoogle(Exception):
    pass


class ErrorSettingAvatar(Exception):
    msg = 'Error setting twitter avatar'

    def __init__(self, scrapper):
        scrapper.logger.error(self.msg)


class CasperJSError(Exception):
    def __init__(self, bot):
        settings.LOGGER.error('CasperJSError - bot %s' % bot.username)


class CasperJSProcessTimeoutError(Exception):
    def __init__(self, bot):
        self.msg = 'CasperJSProcessTimeoutError (exceeded %i secs waiting to terminate) - bot %s' \
                   % (settings.CASPERJS_PROCESS_TIMEOUT, bot.username)
        settings.LOGGER.error(self.msg)


class CasperJSNotFoundElement(Exception):
    def __init__(self, el_str, url):
        settings.LOGGER.error('item %s not found by casperjs' % el_str)


class CasperJSWaitTimeoutExceeded(Exception):
    def __init__(self, sender, waited_for=None, seconds=None):
        self.msg = 'CasperJSWaitTimeoutExceeded on bot %s' % sender.username
        if waited_for:
            self.msg += '. Waited for: %s' % waited_for
        if seconds:
            self.msg += '(%i secs)' % seconds
        settings.LOGGER.warning(self.msg)


class NoStdoutReturned(Exception):
    pass


class PageloadTimeoutExpired(Exception):
    def __init__(self, sender, seconds=None):
        self.msg = 'PageloadTimeoutExpired on bot %s' % sender.username
        if seconds:
            self.msg += ' (%i secs)' % seconds
        settings.LOGGER.warning(self.msg)