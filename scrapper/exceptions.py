from twitter_bots import settings


class TwitterEmailNotFound(Exception):
    pass


class TwitterEmailNotConfirmed(Exception):
    def __init__(self, bot):
        settings.LOGGER.warning('Bot %s hasnt confirmed twitter email %s yet' % (bot.username, bot.email))


class TwitterAccountSuspended(Exception):
    def __init__(self, bot):
        settings.LOGGER.warning('Bot %s has his twitter account suspended' % bot.username)


class BotDetectedAsSpammerException(Exception):
    def __init__(self, bot):
        settings.LOGGER.warning('Bot %s was detected as spammer' % bot.username)
        bot.it_works = False
        bot.save()


class FailureSendingTweetException(Exception):
    pass


class BotMustVerifyPhone(Exception):
    def __init__(self, bot):
        settings.LOGGER.warning('Bot %s must do mobile phone verification' % bot.username)
        bot.must_verify_phone = True
        bot.save()


class RequestAttemptsExceededException(Exception):
    def __init__(self, bot, url):
        settings.LOGGER.warning('Exceeded attemps connecting to %s from bot %s' % (url, bot.username))


class TwitterBotDontExistsOnTwitterException(Exception):
    def __init__(self, bot):
        bot.mark_as_not_twitter_registered_ok()
        settings.LOGGER.warning('Username %s dont exists on twitter' % bot.username)


class NoMoreAvaiableProxiesException(Exception):
    def __init__(self):
        settings.LOGGER.error('There is no more avaiable proxies. Finishing..')