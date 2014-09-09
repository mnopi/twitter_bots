# -*- coding: utf-8 -*-

import random
import time
from . import settings


def _delay(t1, t2, ignore_fast_mode=False):
    if not settings.FAST_MODE or ignore_fast_mode:
        time.sleep(random.uniform(t1, t2))


def seconds(seconds=None, type='box_switch'):
    """
    Crea retardo aleatorio +-0.9-1.8 entre los segundos dados en decimal
    """
    minor = seconds - random.uniform(0.9, 1.8)
    major = seconds + random.uniform(0.9, 1.8)
    if minor < 0: minor = random.uniform(0.1, 0.5)
    if major < 0: major = random.uniform(0.1, 0.5)
    _delay(minor, major, ignore_fast_mode=True)


def box_switch():
    """
    Crea retardo entre que pasa de una casilla a otra del formulario
    """
    _delay(1.0, 2.0)


def key_stroke():
    """
    Crea retardo entre que se pulsa una tecla y otra para rellenar un campo del formulario
    """
    _delay(0.2, 0.6)


def click_after_move():
    """
    Entre que se termina de mover el ratón y se hace click
    """
    _delay(0.3, 1.0)


def during_mousemove():
    """Tiempo mientas se supone que el ratón se desplaza"""
    _delay(0.5, 1.5)