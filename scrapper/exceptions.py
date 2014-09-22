from .logger import LOGGER


class TwitterEmailNotFound(Exception):
    pass


class BotDetectedAsSpammerException(Exception):
    def __init__(self, bot):
        LOGGER.warning('Bot %s was detected as spammer' % bot.username)
        bot.it_works = False
        bot.save()


class BotMustVerifyPhone(Exception):
    def __init__(self, bot):
        LOGGER.warning('Bot %s must do mobile phone verification' % bot.username)
        bot.must_verify_phone = True
        bot.save()


class RequestAttemptsExceededException(Exception):
    def __init__(self, bot, url):
        LOGGER.warning('Exceeded attemps connecting to %s from bot %s' % (url, bot.username))


class TwitterBotDontExistsOnTwitterException(Exception):
    def __init__(self, bot):
        bot.mark_as_not_twitter_registered_ok()
        LOGGER.warning('Username %s dont exists on twitter' % bot.username)


class NoMoreAvaiableProxiesException(Exception):
    def __init__(self):
        LOGGER.error('There is no more avaiable proxies. Finishing..')