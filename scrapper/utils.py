# -*- coding: utf-8 -*-
import threading
from django.utils.timezone import utc
import os
from fake_useragent import UserAgent
import random
import time
import string
import names
import datetime
import requests
from requests.packages.urllib3 import Timeout
import shutil
import simplejson


def generate_random_string(size=None, with_special_chars=False, only_lowercase=False):
    "Para generar por ejemplo las constraseñas"
    str = ''
    types = [
        lambda: random.choice(string.ascii_lowercase),
        lambda: random.choice(string.ascii_uppercase),
        lambda: random.choice(string.digits),
    ]

    if not size:
        size = random.randint(8, 12)

    for i in range(size):
        str += random.choice(types)()

    if with_special_chars:
        # reemplazamos por algunos caracteres especiales
        for _ in range(size/4):
            str[random.randint(0, len(str)-1)] = random.choice('#()/%')

    if only_lowercase:
        str = str.lower()

    return str


def generate_random_full_name():
    """Genera un nombre completo (name + last_name)"""
    return names.get_full_name()


def generate_random_username(full_name=None, gender=None):
    """Genera un usuario aleatorio a partir de su nombre completo. Sirve tanto para usuario de email
    como cuenta de twitter, etc"""
    if not full_name:
        full_name = names.get_full_name(gender)

    first_name = full_name.split(" ")[0]
    last_name = full_name.split(" ")[1]

    first_name_prefix = first_name[0:random.randint(0, 3)].lower()
    last_digits = ''.join(random.choice(string.digits) for i in range(random.randint(0, 3)))
    return first_name_prefix + last_name.lower() + last_digits


def wait_condition(cond, timeout=80, err_msg="Timeout waiting condition"):
    """Se espera hasta un máximo 'timeout' a que ocurra la condición 'cond', que puede tratarse
    de un valor booleano o bien una función a ejecutar cada vez que queramos comprobar su estado"""
    wait_start = utc_now()
    while not cond():
        time.sleep(0.5)
        diff = utc_now() - wait_start
        if diff.seconds >= timeout:
            raise Exception(err_msg)


def check_condition(cond, timeout=5, **kwargs):
    """Mira si se cumple la condición 'cond', dándole por default un timeout de 5 segundos"""
    try:
        wait_condition(cond, timeout=timeout, **kwargs)
        return True
    except Exception:
        return False


def get_element(el_sel_fn):
    """
    Por ejemplo: get_element(lambda: self.get_css_element('#message-drawer'))
    """
    try:
        return el_sel_fn()
    except Exception:
        return None


def get_ex_msg(ex):
    if hasattr(ex, 'message') and ex.message:
        return ex.message
    elif hasattr(ex, 'msg') and ex.msg:
        return ex.msg
    else:
        return ''


def random_date(start_year, end_year):
    """Devuelve una fecha al azar entre 2 años dados"""
    year = random.choice(range(start_year, end_year+1))
    month = random.choice(range(1, 12+1))
    day = random.choice(range(1, 28+1))
    return datetime.datetime(year, month, day)


def generate_random_desktop_user_agent():
    """Pillamos lista de navegadores desde la w3schools, si falla tiramos de user_agents.json
    sólo usamos ff o chrome"""
    from twitter_bots import settings

    def is_desktop_ua(ua):
        return not 'iphone' in ua.lower() and not 'ipad' in ua.lower() and not 'mobile' in ua.lower()

    def get_from_w3schools():
        # primero comprobamos que esté en pie la página
        requests.get('http://w3schools.com', timeout=30)
        ua = UserAgent()
        while True:
            ua = ua.__getattr__(random.choice(['firefox', 'chrome']))
            if is_desktop_ua(ua):
                return ua

    def get_from_json():
        json_data = open(os.path.join(os.path.dirname(__file__), 'user_agents.json'))
        user_agents = simplejson.load(json_data)
        json_data.close()
        while True:
            ua = random.choice(user_agents)
            if is_desktop_ua(ua):
                return ua

    try:
        return get_from_w3schools()
    except Timeout:
        settings.LOGGER.warning('w3schools.com not accesible now, getting from user_agentes.json')
        return get_from_json()


def try_except(fn, ex_msg):
    from twitter_bots import settings

    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception, e:
            settings.LOGGER.exception(ex_msg)
            raise e
    return wrapped


def mkdir_if_not_exists(path_to_dir):
    if not os.path.exists(path_to_dir):
        os.makedirs(path_to_dir)


def rmdir_if_exists(path_to_dir):
    if os.path.exists(path_to_dir):
        shutil.rmtree(path_to_dir)


def create_file_if_not_exists(file):
    if not os.path.exists(file):
        open(file, 'w').close()


class QuoteGenerator(object):
    def get_quote(self):
        pass

def get_thread_name():
    return '###%s### - ' % threading.current_thread().name


def naive_to_utc(datetime):
    return datetime.replace(tzinfo=utc)


def utc_now():
    return naive_to_utc(datetime.datetime.utcnow())


def compare_datetimes(d1, d2):
    # limpiamos ambas fechas a naive por si están en UTC, etc
    d1 = d1.replace(tzinfo=None)
    d2 = d2.replace(tzinfo=None)
    if d1 > d2:
        # si d1 es más nueva que d2
        return 1
    elif d1 == d2:
        return 0
    elif d1 < d2:
        # si d1 es más antigua que d2
        return -1


def is_older(d1, d2):
    """Nos dice si la fecha d1 es más vieja que d2"""
    return compare_datetimes(d1, d2) == -1


def is_newer(d1, d2):
    """Nos dice si la fecha d1 es más nueva que d2"""
    return compare_datetimes(d1, d2) == 1


def is_gte_than_days_ago(given_datetime, days_ago):
    "Nos dice si la fecha dada es igual o más nueva que la de este momento hace days_ago"
    datetime_days_ago = utc_now() - datetime.timedelta(days=days_ago)
    return not is_older(given_datetime, datetime_days_ago)


def is_lte_than_seconds_ago(given_datetime, seconds_ago):
    "Nos dice si la fecha dada es más antigua o igual que la de este momento hace seconds_ago"
    datetime_seconds_ago = utc_now() - datetime.timedelta(seconds=seconds_ago)
    return not is_newer(given_datetime, datetime_seconds_ago)


def is_lte_than_days_ago(given_datetime, days_ago):
    return is_lte_than_seconds_ago(given_datetime, days_ago * 24 * 60 * 60)