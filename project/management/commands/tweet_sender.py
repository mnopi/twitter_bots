# -*- coding: utf-8 -*-
from Queue import Full

from optparse import make_option
import socket
import time
from celery.exceptions import TimeoutError
import psutil
from core.models import TwitterBot
from core.scrapper.utils import get_2_args
from project.models import Tweet, Project
from project.exceptions import FatalError, ProjectRunningWithoutBots
from twitter_bots import settings
from django.core.management.base import BaseCommand
from twitter_bots.settings import set_logger


MODULE_NAME = __name__.split('.')[-1]

host = socket.gethostname()

celery_tasks = []

def do_process_mention(mention_pk):
    from core import tasks
    # from django.db import connection
    #
    # connection.close()
    # mention = Tweet.objects.get(pk=mention_pk)
    try:
        task = tasks.process_mention.apply_async(args=(mention_pk,))
        celery_tasks.append(task)
        settings.LOGGER.info('Mention %s -> celery' % mention_pk)
    except TimeoutError:
        settings.LOGGER.exception('timeouterror processing mention %s on celery queue' % mention_pk)


def test1(mention_pk):
    time.sleep(4)
    settings.LOGGER.info('mention: %s' % mention_pk)


def process_mention(mention_id):
    """Esta función es lo que se ejecutará en cada uno de los nodos.
    Invocará al comando manage.py mention_processor, ubicado en el correspondiente nodo"""

    from threading import Timer
    import socket, subprocess

    HOSTS = {
        'p1': {
            'manage.py': '/home/robots/Dropbox/dev/proyectos/twitter_bots/manage.py',
        },
        'rmaja': {
            'python': '/home/rmaja/virtualenvs/twitter_bots/bin/python',
            'manage.py': '/home/rmaja/Dropbox/dev/proyectos/twitter_bots/manage.py',
        },
        'gallina1': {}
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


def call_process_mention_command(mention, cluster):
    job = cluster.submit(mention.pk)
    job.id = mention.pk
    settings.LOGGER.info('Executing job id=%i..' % job.id)
    job()
    if job.exception:
        settings.LOGGER.error('Error executing job id=%i: %s' % (job.id, job.exception))
    else:
        host, result = job.result
        settings.LOGGER.info('..job %i executed on host %s with result: %s' % (job.id, host, result))
    # cluster.wait()


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

            max_lookups, max_tweets = get_2_args(args)

            TwitterBot.objects.perform_sending_tweets(bot=bot, max_tweets=max_tweets, max_lookups=max_lookups)

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

