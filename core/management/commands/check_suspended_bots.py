# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from core.models import TwitterBot
from scrapper.accounts.twitter import TwitterScrapper


class Command(BaseCommand):
    help = u'Comprueba si los usuarios que todavía están marcados como "it_works" siguen activos'

    def handle(self, *args, **options):
        bots_to_check = TwitterBot.objects.filter(it_works=True)

        for bot in bots_to_check:
            TwitterScrapper(bot).check_account_suspended()
