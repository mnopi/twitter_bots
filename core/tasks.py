from __future__ import absolute_import

from celery import shared_task
import time
from core.models import TwitterBot
from project.models import Tweet
from twitter_bots import settings


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
def tarea1(sleep):
    """http://stackoverflow.com/a/26687086"""
    time.sleep(sleep)
    return TwitterBot.objects.last().username


@shared_task
def process_mention(mention_pk):
    settings.set_logger('project.management.commands.tweet_sender')
    mention = Tweet.objects.get(pk=mention_pk)
    mention.process_sending()