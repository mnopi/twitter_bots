# -*- coding: utf-8 -*-
import os

MNOPI_PROXY = "54.197.231.98:8000"

TOR_CTRL_PORT = 9051
TOR_PORT = 9050
TOR_PROXY = "127.0.0.1:%s" % str(TOR_PORT)

PHANTOMJS_PATH = '/Users/rmaja/phantomjs-1.9.7-macosx/bin/phantomjs'
CHROMEDRIVER_PATH = '/Users/rmaja/chromedriver'

DEATHBYCAPTCHA_USER = 'deathbychucknorris'
DEATHBYCAPTCHA_PASSWORD = 'eS9WsRzFv8'

URLS = {
    'twitter_reg': 'https://twitter.com/signup',
    'twitter_login': 'https://twitter.com',
    'hushmail_reg': 'https://www.hushmail.com/signup/',
    'hushmail_login': 'https://www.hushmail.com/preview/hushmail/',
    'gmail_reg': 'https://accounts.google.com/SignUp',
    'gmail_login': 'https://www.hushmail.com/preview/hushmail/',
    'hotmail_reg': 'https://signup.live.com/',
    'hotmail_login': 'https://outlook.com',
}

COMPATIBLE_EMAIL_ACCOUNTS = [
    'hushmail.com',
    'gmail.com',
    'hotmail.com'
]


### TOR MODE !!
###############
TOR_MODE = False
###############
FAST_MODE = False  # para saltarse los delays en testeo


MANUAL_MODE = False
REGISTER_EMAIL = True  # para activar o no el registro del email
TW_CONFIRM_EMAIL = True  # para activar o no el leer el email de confirmación de twitter

# si no activamos registro de email evidentemente no haremos la confirmación
if not REGISTER_EMAIL:
    TW_CONFIRM_EMAIL = False

MAX_THREADS = 3  # máximo de hilos para procesar los bots
USE_PROXY = True

BIRTH_INTERVAL = (1975, 1995)  # intervalo para elegir aleatoriamente la fecha de nacimiento del bot

#driver = webdriver.PhantomJS(CHROMEDRIVER_PATH)
#driver = webdriver.Chrome(CHROMEDRIVER_PATH)

MAX_TWT_BOTS_PER_PROXY = 2

# mínimo de días que tienen que pasar para que un bot se registre después de el anterior usando el mismo proxy
DAYS_BETWEEN_REGISTRATIONS_PER_PROXY = 5

PAGE_LOAD_TIMEOUT = 35
EMAIL_ACCOUNT_TYPE = 'hotmail.com'

RANDOM_OFFSETS_ON_EL_CLICK = False  # activar offset al hacer click con el ratón sobre un elemento dado
TYPING_SPEED = (20, 40)  # en ms, el tiempo que pasa entre que se presiona/levanta una tecla


if TOR_MODE:
    FAST_MODE = True
    USE_PROXY = True
    REGISTER_EMAIL = True
    TW_CONFIRM_EMAIL = True

# FI (firefox)
# CH (chrome)
# PH (phantomjs)
# WEBDRIVER = 'FI'
WEBDRIVER = 'PH'