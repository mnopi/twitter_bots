# -*- coding: utf-8 -*-
import re
import datetime

from django.db import models
import time
from django.db.models import Q
from scrapper import settings, Scrapper
from scrapper.settings import REUSE_BOTS, TOR_MODE
from twitter_bots.settings import LOGGER


class TwitterBotManager(models.Manager):
    # def create(self, **kwargs):
    #
    #     super(TwitterBotManager, self).create(**kwargs)

    def get_not_registered_ok_bots(self, num_bots=None):
        """
        Coje todos los bots que no se hayan registrado del todo, es decir aquellos que:
            NO cumplan alguna de las siguientes condiciones:
                - no hayan creado su email
                - no hayan creado su twitter
                - no hayan confirmado su email en twitter y además no tengan marcado como "no recibido" dicho email de confirmación,
                    ya que hay usuarios a los que twitter no se los manda (puede ser por tema de la IP)
            Y cumplan las siguientes:
                - no esté marcado como spam por twitter (it_works)
                - no sea un bot creado manualmente para pruebas
        """
        bots = self.filter(
            (Q(email_registered_ok=False) | Q(twitter_registered_ok=False) | Q(twitter_confirmed_email_ok=False)),
            it_works=True,
            is_manually_registered=False
        )

        if TOR_MODE:
            bots = bots.filter(proxy='tor')

        if num_bots:
            return list(bots[:num_bots])
        else:
            return list(bots)

    def create_new_bot(self):
        """Mira qué proxy hay sin usar y devuelve objeto TwitterBot con ese proxy ya reservado"""
        empty_bot = self.create()
        empty_bot.populate()
        empty_bot.assign_proxy()
        return empty_bot

    def create_new_bots(self, num_bots):
        """Devuelve una lista de bots con sus respectivos proxies ya reservados"""
        return [self.create_new_bot() for _ in range(0, num_bots)]

    def create_new_bots_including_reusable(self, num_bots):
        """Devuelve bots reusables a partir de un número de bots dado"""
        reusable_bots = self.get_not_registered_ok_bots()[:num_bots]

        # sólo asignamos proxies nuevamente a aquellos bots que no tengan ninguna cuenta registrada
        for b in reusable_bots:
            if b.has_no_accounts() and not b.proxy:
                b.assign_proxy()

        num_new_bots = num_bots - len(reusable_bots)
        new_bots = self.create_new_bots(num_new_bots)
        return reusable_bots + new_bots

    def create_bots(self, num_bots):
        if REUSE_BOTS:
            return self.create_new_bots_including_reusable(num_bots)
        else:
            return self.create_new_bots(num_bots)

