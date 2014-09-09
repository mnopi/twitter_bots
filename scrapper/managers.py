# -*- coding: utf-8 -*-
import os

from django.db import models
from twitter_bots import settings
from twitter_bots.settings import LOGGER


class TwitterBotManager(models.Manager):
    def create_new_bot(self):
        """Mira qué proxy hay sin usar y devuelve objeto TwitterBot con ese proxy ya reservado"""
        empty_bot = self.create()
        empty_bot.populate()
        empty_bot.assign_proxy()
        return empty_bot

    def create_bots(self, num_bots):
        """Devuelve una lista de bots con sus respectivos proxies ya reservados"""
        return [self.create_new_bot() for _ in range(0, num_bots)]

    def check_listed_proxy(self, proxy):
        """Mira si el proxy está en las listas de proxies actuales, por si el usuario no se usó hace
        mucho tiempo y se refrescó la lista de proxies con los proveedores, ya que lo hacen cada mes normalmente"""
        if not settings.TOR_MODE:
            found_listed_proxy = False
            proxies_folder = os.path.join(settings.PROJECT_ROOT, 'core', 'proxies')
            for (dirpath, dirnames, filenames) in os.walk(proxies_folder):
                if found_listed_proxy: break
                for filename in filenames:  # myprivateproxy.txt
                    if found_listed_proxy: break
                    with open(os.path.join(dirpath, filename)) as f:
                        proxies_lines = f.readlines()
                        for pl in proxies_lines:
                            pl = pl.replace('\n', '')
                            pl = pl.replace(' ', '')
                            if pl == proxy:
                                found_listed_proxy = True
                                break

            if not found_listed_proxy:
                LOGGER.info('Proxy %s @ %s not listed' % (self.proxy, self.proxy_provider))

            return found_listed_proxy
        else:
            # si estamos en modo TOR siempre vamos a decir que el proxy está en listas
            return True