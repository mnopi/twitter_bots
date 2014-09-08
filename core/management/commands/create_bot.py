# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from core.models import TwitterBot
from scrapper import Scrapper
import threading


class Command(BaseCommand):
    help = u'Comprueba si los usuarios que todavía están marcados como "it_works" siguen activos'

    def handle(self, *args, **options):
        TwitterBot.objects.create()