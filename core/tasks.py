from __future__ import absolute_import

from celery import shared_task
import time
from core.models import TwitterBot


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
def tarea1(numbers):
    time.sleep(10)
    return TwitterBot.objects.first().username