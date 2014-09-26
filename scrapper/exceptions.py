from .logger import LOGGER


class TwitterEmailNotFound(Exception):
    pass


class BotDetectedAsSpammerException(Exception):
    def __init__(self, bot):
        settings.LOGGER.warning('Bot %s was detected as spammer' % bot.username)
        bot.it_works = False
        bot.save()


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