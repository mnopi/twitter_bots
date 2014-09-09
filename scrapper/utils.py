# -*- coding: utf-8 -*-
import os
from fake_useragent import UserAgent
import random
import time
import string
import names
import datetime
import requests
from requests.packages.urllib3 import Timeout
import simplejson
from .logger import LOGGER


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


def wait_condition(cond, timeout=30, err_msg="Timeout waiting condition"):
    """Se espera hasta un máximo 'timeout' a que ocurra la condición 'cond', que puede tratarse
    de un valor booleano o bien una función a ejecutar cada vez que queramos comprobar su estado"""
    wait_start = datetime.datetime.now()
    while not cond():
        time.sleep(0.5)
        diff = datetime.datetime.now() - wait_start
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
    def is_desktop_ua(ua):
        return not 'iphone' in ua.lower() and not 'ipad' in ua.lower() and not 'mobile' in ua.lower()

    def get_from_w3schools():
        # primero comprobamos que esté en pie la página
        requests.get('http://w3schools.com', timeout=10)
        ua = UserAgent()
        ua.update()
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
        LOGGER.warning('w3schools.com not accesible now, getting from user_agentes.json')
        return get_from_json()


def try_except(fn, ex_msg):
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception, e:
            LOGGER.exception(ex_msg)
            raise e
    return wrapped


def mkdir_if_not_exists(path_to_dir):
    if not os.path.exists(path_to_dir):
        os.makedirs(path_to_dir)


def create_file_if_not_exists(file):
    if not os.path.exists(file):
        open(file, 'w').close()
