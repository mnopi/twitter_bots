# -*- coding: utf-8 -*-


from __future__ import absolute_import
import socket

from celery import shared_task
from celery.exceptions import TimeoutError
from django.db import connection
from twitter_bots import settings


def log_task_adding_to_celery(task_descr):
        settings.LOGGER.info('Task [%s] -> celery' % task_descr)

def log_task_timeout_on_celery(task_descr):
    settings.LOGGER.exception('TimeoutError processing on celery queue: %s' % task_descr)

def log_task_processed_on_celery(task_descr):
    settings.LOGGER.info('-- Task |%s| processed --' % task_descr)

def log_celery_task_result(task):
    if task.failed():
        settings.LOGGER.warning('-- Task %s failed' % task.task_id)
    elif task.result:
        host, output = task.result
        settings.LOGGER.info('-- Task %s processed. host: %s, output: %s' % (task.task_id, host, output))
    else:
        settings.LOGGER.warning('Task %s not failed without result' % task.task_id)


class CeleryTasksManager(object):
    def __init__(self):
        self.celery_tasks_tweet_sender = []

    def add_task__send_mutweet(self, mutweet, burst_limit):
        task_descr = 'send_mutweet %i' % mutweet.pk

        try:
            task = send_as_mutweet.apply_async(args=(mutweet.pk,), kwargs={'burst_limit': burst_limit})
            self.celery_tasks_tweet_sender.append(task)
            log_task_adding_to_celery(task_descr)
        except TimeoutError:
            log_task_timeout_on_celery(task_descr)

    def add_task__verify_mctweet_if_received_ok(self, mctweet):
        destination_bot = mctweet.mentioned_bots.first()
        task_descr = '%s verify_mctweet_if_received_ok %i from %s' \
                     % (destination_bot.username, mctweet.pk, mctweet.bot_used.username)

        try:
            task = verify_mctweet_if_received_ok.apply_async(args=(mctweet.pk,))
            self.celery_tasks_tweet_sender.append(task)
            log_task_adding_to_celery(task_descr)
        except TimeoutError:
            log_task_timeout_on_celery(task_descr)

    def add_task__send_single_tweet(self, tweet):
        task_descr = 'send_single_tweet %i [%s]' % (tweet.pk, tweet.print_type())

        try:
            task = send_single_tweet.apply_async(args=(tweet.pk,))
            self.celery_tasks_tweet_sender.append(task)
            log_task_adding_to_celery(task_descr)
        except TimeoutError:
            log_task_timeout_on_celery(task_descr)

    def add_task__follow_twitterusers(self, bot):
        task_descr = '%s follow_twitterusers' % bot.username

        try:
            task = follow_twitterusers.apply_async(args=(bot.pk,))
            self.celery_tasks_tweet_sender.append(task)
            log_task_adding_to_celery(task_descr)
        except TimeoutError:
            log_task_timeout_on_celery(task_descr)


@shared_task
def add(x, y):
    return x + y


@shared_task
def mul(x, y):
    return x * y


@shared_task
def xsum(numbers):
    return sum(numbers)



@shared_task
def process_mention(mention_pk):
    from project.models import Tweet

    try:
        settings.set_logger('project.management.commands.tweet_sender')
        mention = Tweet.objects.get(pk=mention_pk)
        output = mention.process_sending()
        settings.LOGGER.info('-- Mention %i processed --' % mention_pk)
        return socket.gethostname(), output
    finally:
        connection.close()


@shared_task()
def send_as_mutweet(mention_pk, burst_limit=None):
    from project.models import Tweet

    try:
        settings.set_logger('project.management.commands.tweet_sender')
        mention = Tweet.objects.get(pk=mention_pk)
        output = mention.send_as_mutweet(burst_limit)
        log_task_processed_on_celery('send_as_mutweet %i' % mention_pk)
        return socket.gethostname(), output
    finally:
        connection.close()


@shared_task()
def verify_mctweet_if_received_ok(mctweet_pk):
    from project.models import Tweet

    try:
        settings.set_logger('project.management.commands.tweet_sender')
        mctweet = Tweet.objects.get(pk=mctweet_pk)
        mentioned_bot = mctweet.mentioned_bots.first()
        output = mentioned_bot.verify_mctweet_if_received_ok(mctweet)
        log_task_processed_on_celery('verify_mctweet_if_received_ok %i' % mctweet_pk)
        return socket.gethostname(), output
    finally:
        connection.close()


@shared_task()
def send_single_tweet(tweet_pk):
    from core.scrapper.exceptions import BotNotLoggedIn
    from project.models import Tweet

    try:
        settings.set_logger('project.management.commands.tweet_sender')
        tweet = Tweet.objects.get(pk=tweet_pk)
        sender = tweet.bot_used
        sender.set_cookies_files_for_casperjs()
        try:
            output = tweet.send()
            tweet.save()
        except BotNotLoggedIn as e:
            # si al enviar con casperjs resulta que el bot no está logueado se loguea con selenium
            sender.login_twitter_with_webdriver()
            output = 'Bot %s (%s) needed to login twitter before sending tweet %d [%s]' \
                     % (sender.username, sender.real_name, tweet.pk, tweet.print_type())

        log_task_processed_on_celery('send_single_tweet %i [%s]' % (tweet_pk, tweet.print_type()))
        return socket.gethostname(), output
    finally:
        connection.close()


@shared_task()
def follow_twitterusers(bot_pk):
    from core.models import TwitterBot

    try:
        settings.set_logger('project.management.commands.tweet_sender')
        bot = TwitterBot.objects.get(pk=bot_pk)
        output = bot.follow_twitterusers()
        log_task_processed_on_celery('%s follow_twitterusers' % bot.username)
        return socket.gethostname(), output
    finally:
        connection.close()