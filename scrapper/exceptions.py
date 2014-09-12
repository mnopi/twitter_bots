from .logger import LOGGER


class TwitterEmailNotFound(Exception):
    pass


class BotDetectedAsSpammerException(Exception):
    def __init__(self, bot):
        LOGGER.warning('Bot %s was detected as spammer' % bot.username)
        bot.it_works = False
        bot.save()