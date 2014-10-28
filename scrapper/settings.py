# -*- coding: utf-8 -*-
import os

MNOPI_PROXY = "54.197.231.98:8000"

TOR_CTRL_PORT = 9051
TOR_PORT = 9050
TOR_PROXY = "127.0.0.1:%s" % str(TOR_PORT)

CHROMEDRIVER_PATH = '/Users/rmaja/chromedriver'


DEATHBYCAPTCHA_USER = 'deathbychucknorris'
DEATHBYCAPTCHA_PASSWORD = 'eS9WsRzFv8'

URLS = {
    'twitter_reg': 'https://twitter.com/signup/',
    'twitter_login': 'https://twitter.com/',
    'hushmail_reg': 'https://www.hushmail.com/signup/',
    'hushmail_login': 'https://www.hushmail.com/preview/hushmail/',
    'gmail_reg': 'https://accounts.google.com/SignUp/',
    'gmail_login': 'https://www.hushmail.com/preview/hushmail/',
    'hotmail_reg': 'https://signup.live.com/',
    'hotmail_login': 'https://outlook.com/',
}

COMPATIBLE_EMAIL_ACCOUNTS = [
    'hushmail.com',
    'gmail.com',
    'hotmail.com'
]


### TOR MODE && TEST MODE !!
###############
TOR_MODE = False
TEST_MODE = False
FORCE_FIREFOX = False
###############
FAST_MODE = False  # para saltarse los delays en testeo
TAKE_SCREENSHOTS = True


REGISTER_EMAIL = True  # para activar o no el registro del email
TW_CONFIRM_EMAIL = True  # para activar o no el leer el email de confirmación de twitter
TW_SET_AVATAR = True
TW_SET_BIO = True

# si no activamos registro de email evidentemente no haremos la confirmación
if not REGISTER_EMAIL:
    TW_CONFIRM_EMAIL = False

MAX_THREADS_SENDING_TWEETS = 70  # máximo de hilos para enviar tweets
MAX_THREADS_EXTRACTING_FOLLOWERS = 3
MAX_THREADS_CREATING_BOTS = 50  # máximo de hilos para crear bots
MAX_THREADS_COMPLETING_PENDANT_BOTS = 4  # máximo de hilos para restaurar creación de robots todavía a medias
PENDING_TWEETS_QUEUE_SIZE = MAX_THREADS_SENDING_TWEETS * 10  # tamaño máximo de la cola para enviar tweets

TIME_WAITING_FREE_QUEUE = 5  # cada x segundos se comprueba si hay espacio en la cola para crear nuevos tweets
TIME_WAITING_AVAIABLE_BOT_TO_TWEET = 5  # cada x segundos el enviador de tweets comprueba que haya bots disponibles para enviarlos

USE_PROXY = True

BIRTH_INTERVAL = (1975, 1995)  # intervalo para elegir aleatoriamente la fecha de nacimiento del bot

#driver = webdriver.PhantomJS(CHROMEDRIVER_PATH)
#driver = webdriver.Chrome(CHROMEDRIVER_PATH)

MAX_TWT_BOTS_PER_PROXY_FOR_REGISTRATIONS = 6  # máximo de robots que pueden haber creados a la vez desde misma ip
MAX_TWT_BOTS_PER_PROXY_FOR_LOGIN = 12  # máximo de robots que se pueden loguear a la vez desde una misma ip

# mínimo de días que tienen que pasar para que un bot se registre después de el anterior usando el mismo proxy
MIN_DAYS_BETWEEN_REGISTRATIONS_PER_PROXY = 5

PAGE_LOAD_TIMEOUT = 300
EMAIL_ACCOUNT_TYPE = 'hotmail.com'

RANDOM_OFFSETS_ON_EL_CLICK = False  # activar offset al hacer click con el ratón sobre un elemento dado
TYPING_SPEED = (20, 40)  # en ms, el tiempo que pasa entre que se presiona/levanta una tecla

# FI (firefox)
# CH (chrome)
# PH (phantomjs)
# WEBDRIVER = 'FI'
WEBDRIVER = 'PH'

if TOR_MODE:
    FAST_MODE = True
    USE_PROXY = True
    REGISTER_EMAIL = True
    TW_CONFIRM_EMAIL = True

if TEST_MODE:
    FAST_MODE = True
    WEBDRIVER = 'FI'
    TAKE_SCREENSHOTS = True