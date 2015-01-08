# -*- coding: utf-8 -*-

import random
import time
from . import settings


class Delay(object):
    def __init__(self, user):
        self.user = user

    def _delay(self, t1, t2, force_delay=False):
        if force_delay or not settings.FAST_MODE:
            time.sleep(random.uniform(t1, t2))

    def seconds(self, seconds=None, type='box_switch', force_delay=False):
        """
        Crea retardo aleatorio +-0.9-1.8 entre los segundos dados en decimal
        """
        minor = seconds - random.uniform(0.9, 1.8)
        major = seconds + random.uniform(0.9, 1.8)
        if minor < 0: minor = random.uniform(0.1, 0.5)
        if major < 0: major = random.uniform(0.1, 0.5)
        self._delay(minor, major, force_delay=force_delay)

    def box_switch(self):
        """
        Crea retardo entre que pasa de una casilla a otra del formulario
        """
        self._delay(1.0, 2.0)


    def key_stroke(self):
        """
        Crea retardo entre que se pulsa una tecla y otra para rellenar un campo del formulario
        """
        self._delay(0.2, 0.6)


    def click_after_move(self):
        """
        Entre que se termina de mover el ratón y se hace click
        """
        self._delay(0.3, 1.0)


    def during_mousemove(self):
        """Tiempo mientas se supone que el ratón se desplaza"""
        self._delay(0.5, 1.5)