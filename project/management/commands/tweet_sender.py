# -*- coding: utf-8 -*-
from Queue import Full

from optparse import make_option
import time
import psutil
from core.models import TwitterBot
from core.scrapper.utils import get_2_args
from project.models import Tweet, Project
from project.exceptions import FatalError, ProjectRunningWithoutBots
from twitter_bots import settings
from django.core.management.base import BaseCommand
from twitter_bots.settings import set_logger


MODULE_NAME = __name__.split('.')[-1]

# CLIENT_IP_PRIVATE = '192.168.1.115'
# CLIENT_IP_PUBLIC = '88.26.212.82'
CLIENT_IP_PRIVATE = '192.168.0.115'
CLIENT_IP_PUBLIC = '77.228.76.30'

DISPY_NODES = [
    # '46.101.61.145',  # gallina1
    '88.26.212.82',  # pepino1
    CLIENT_IP_PRIVATE,  # local
    # '*',
]


def process_mention(mention_id):
    from threading import Timer
    import time, socket, subprocess
    # settings.LOGGER.info('Processing mention %i..' % mention_id)
    # Tweet.objects.process_mention(mention_id)
    HOSTS = {
        'p1': {
            'manage.py': '/home/robots/Dropbox/dev/proyectos/twitter_bots/manage.py',
        },
        'rmaja': {
            'python': '/home/rmaja/virtualenvs/twitter_bots/bin/python',
            'manage.py': '/home/rmaja/Dropbox/dev/proyectos/twitter_bots/manage.py',
        }
    }

    # estos son los paths por defecto para intérprete y manage.py
    DEFAULTS = {
        'python': '/home/robots/virtualenvs/twitter_bots/bin/python',
        'manage.py': '/home/robots/prod/twitter_bots/manage.py',
    }

    host = socket.gethostname()

    command = [
        HOSTS[host].get('python', DEFAULTS['python']),
        HOSTS[host].get('manage.py', DEFAULTS['manage.py']),
        'mention_processor',
        str(mention_id),
        '--settings=twitter_bots.settings_prod'
    ]

    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    timer = Timer(60*5, proc.kill)  # ponemos timeout de x minutos al proceso
    timer.start()
    stdout, stderr = proc.communicate()
    if timer.is_alive():
        timer.cancel()
        return host, stdout or stderr
    else:
        # si el timer agota la espera
        return host, 'Timeout exceeded processing mention %i' % mention_id

    # time.sleep(7)
    # settings.LOGGER.info('..mention %i processed ok' % mention_id)
    # return host, mention_id
    # return 'hola',  44


cluster = None


class Command(BaseCommand):
    help = 'Send pending tweets'

    option_list = BaseCommand.option_list + (
        make_option('--bot',
            dest='bot',
            help='Send pending tweets only from given bot'),
        )

    def handle(self, *args, **options):
        set_logger(__name__)
        settings.LOGGER.info('-- INITIALIZED %s --' % MODULE_NAME)

        try:
            Tweet.objects.clean_not_ok()
            TwitterBot.objects.filter(is_being_used=True).update(is_being_used=False)
            Project.objects.check_bots_on_all_running()

            bot = TwitterBot.objects.get(username=options['bot']) \
                if 'bot' in options and options['bot'] \
                else None

            if bot:
                settings.TAKE_SCREENSHOTS = True

            num_processes, max_lookups = get_2_args(args)

            TwitterBot.objects.perform_sending_tweets(bot=bot, num_processes=num_processes, max_lookups=max_lookups)

            time.sleep(settings.TIME_SLEEPING_FOR_RESPAWN_TWEET_SENDER)
        except Full as e:
            settings.LOGGER.warning('Timeout exceeded, full threadpool queue')
            raise FatalError(e)
        except ProjectRunningWithoutBots:
            pass
        except Exception as e:
            raise FatalError(e)
        finally:
            # quitamos todos los phantomjs que hayan quedado ejecutándose
            phantomjs_to_kill = 'phantomjs_prod' if settings.PROD_MODE else 'phantomjs_dev'
            settings.LOGGER.debug('Killing all %s running processes..' % phantomjs_to_kill)
            for proc in psutil.process_iter():
                if phantomjs_to_kill in proc.name():
                    proc.kill()

        settings.LOGGER.info('-- FINISHED %s --' % MODULE_NAME)

