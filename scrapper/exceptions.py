import time
import datetime
from twitter_bots import settings


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
        bot.proxy.date_phone_required = datetime.datetime.utcnow()
        bot.proxy.save()
        settings.LOGGER.warning('Bot %s must do mobile phone verification' % bot.username)


class RequestAttemptsExceededException(Exception):
    def __init__(self, bot, url):
        settings.LOGGER.warning('Exceeded attemps connecting to %s from bot %s' % (url, bot.username))


class TwitterBotDontExistsOnTwitterException(Exception):
    def __init__(self, bot):
        bot.mark_as_not_twitter_registered_ok()
        settings.LOGGER.warning('Username %s dont exists on twitter' % bot.username)


class NoMoreAvaiableProxiesForCreatingBots(Exception):
    def __init__(self):
        settings.LOGGER.error('There is no more avaiable proxies for creating new bots. Sleeping..')
        time.sleep(120)


class FatalError(Exception):
    def __init__(self):
        settings.LOGGER.exception('FATAL ERROR')
        time.sleep(10)
