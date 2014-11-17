# -*- coding: utf-8 -*-
import os

PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

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


#
# SCRAPPER SETTINGS
USE_PROXY = True
PAGE_LOAD_TIMEOUT = 300  # segundos que se espera a la respuesta al pedir una URL
RANDOM_OFFSETS_ON_EL_CLICK = False  # activar offset al hacer click con el ratón sobre un elemento dado
TYPING_SPEED = (20, 40)  # en ms, el tiempo que pasa entre que se presiona/levanta una tecla
WEBDRIVER = 'PH'
### TOR MODE && TEST MODE !!
###############
TOR_MODE = False
TEST_MODE = False
FORCE_FIREFOX = False
###############
FAST_MODE = False  # para saltarse los delays en testeo
TAKE_SCREENSHOTS = True

#
# EXTRACTORS
## followers
EXTRACT_FOLLOWERS = True
MAX_DAYS_SINCE_REGISTERED_ON_TWITTER_WITHOUT_TWEETS = 50  # máximo de días desde que el usuario se registró y todavía no envió ningún tweet
MAX_DAYS_SINCE_LAST_TWEET = 90  # máximo de días desde que el usuario twiteó por última vez
MAX_PAGE_BREAKS_EXTRACTING_FOLLOWERS = 3  # a los x pagebreaks marca el target_user como extraído y pasa al siguiente
## hashtags
EXTRACT_HASHTAGS = False
MAX_DAYS_FOR_OLDER_TWEET_IN_HASHTAGS = 5
MAX_USER_COUNT_FOR_HASHTAGS = 5000

#
# TWEET CREATOR
TIME_WAITING_FREE_QUEUE = 20  # cada x segundos se comprueba si hay espacio en la cola para crear nuevos tweets
TIME_WAITING_NEW_TWITTEABLE_BOTS = 120
MAX_MENTIONS_PER_TWEET = 1
MAX_QUEUED_TWEETS_TO_SEND_PER_BOT = 3

#
# TWEET SENDER
MAX_THREADS_SENDING_TWEETS = 70  # máximo de hilos para enviar tweets
TOTAL_TASKS_SENDING_TWEETS = MAX_THREADS_SENDING_TWEETS * 10  # número total de tareas para las hebras por cada vez que se ejecuta el proceso de enviar tweets
TIME_WAITING_AVAIABLE_BOT_TO_TWEET = 20  # cada x segundos el enviador de tweets comprueba que haya bots disponibles para enviarlos
MAX_TWT_BOTS_PER_PROXY_FOR_USAGE = 16  # máximo de robots que se pueden loguear a la vez desde una misma ip
TIME_BETWEEN_TWEETS = (2, 7)  # el bot twitea cada x segundos escogidos aleatoriamente en el intervalo de minutos dado

#
# BOT CREATOR
MAX_THREADS_CREATING_BOTS = 50  # máximo de hilos para crear bots
MAX_TWT_BOTS_PER_PROXY_FOR_REGISTRATIONS = 6  # máximo de robots que pueden haber creados a la vez desde misma ip
MIN_DAYS_BETWEEN_REGISTRATIONS_PER_PROXY = 5  # mínimo de días que tienen que pasar para registrar 2 robots desde misma ip
BIRTH_INTERVAL = (1975, 1995)  # intervalo para elegir aleatoriamente la fecha de nacimiento del bot
EMAIL_ACCOUNT_TYPE = 'hotmail.com'
REGISTER_EMAIL = True  # para activar o no el registro del email
TW_CONFIRM_EMAIL = True  # para activar o no el leer el email de confirmación de twitter
TW_SET_AVATAR = True
TW_SET_BIO = True
# si no activamos registro de email evidentemente no haremos la confirmación
if not REGISTER_EMAIL:
    TW_CONFIRM_EMAIL = False

#
# BOT CREATION FINISHER
MAX_THREADS_COMPLETING_PENDANT_BOTS = 4  # máximo de hilos para restaurar creación de robots todavía a medias


#
# PATHS
WEBDRIVERS_PATH = os.path.join(PROJECT_ROOT, 'scrapper', 'webdrivers')

PHANTOMJS_PATH = os.path.join(WEBDRIVERS_PATH, 'phantomjs')
PHANTOMJS_BIN_PATH = os.path.join(PHANTOMJS_PATH, 'phantomjs_mac_bin')

SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, 'scrapper', 'screenshots')
AVATARS_DIR = os.path.join(PROJECT_ROOT, 'scrapper', 'avatars')
PHANTOMJS_COOKIES_DIR = os.path.join(PHANTOMJS_PATH, 'cookies')
PROXIES_DIR = os.path.join(PROJECT_ROOT, 'core', 'proxies')
# by default in /Users/<User>/Library/Application Support/Ofi Labs/PhantomJS
# PHANTOMJS_LOCALSTORAGES_PATH = os.path.join(PHANTOMJS_PATH, 'localstorages')


# FI (firefox)
# CH (chrome)
# PH (phantomjs)
# WEBDRIVER = 'FI'

if TOR_MODE:
    FAST_MODE = True
    USE_PROXY = True
    REGISTER_EMAIL = True
    TW_CONFIRM_EMAIL = True

if TEST_MODE:
    FAST_MODE = True
    WEBDRIVER = 'FI'
    TAKE_SCREENSHOTS = True