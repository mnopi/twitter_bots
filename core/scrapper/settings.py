# -*- coding: utf-8 -*-
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

MNOPI_PROXY = "54.197.231.98:8000"

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
PAGE_LOAD_TIMEOUT = 120  # segundos que se espera a la respuesta al pedir una URL
PAGE_LOAD_TIMEOUT_SENDING_TWEETS = 40  # segundos que casperjs espera a que se cargue twitter para enviar tweet
CASPERJS_PROCESS_TIMEOUT = 120  # segundos que esperamos como maximo para que casperjs termine de ejecutarse desde su invocacion
PAGE_READYSTATE_TIMEOUT = 90  # segundos que se espera a que el DOM de la página esté listo
RANDOM_OFFSETS_ON_EL_CLICK = False  # activar offset al hacer click con el ratón sobre un elemento dado
TYPING_SPEED = (20, 40)  # en ms, el tiempo que pasa entre que se presiona/levanta una tecla
WEBDRIVER = 'PH'
FORCE_FIREFOX = False
###############
TAKE_SCREENSHOTS = True


################
# EXTRACTORS
################

# máximo de días que un twitteruser puede estar en BD sin ser mencionado
MAX_DAYS_TO_STAY_UNMENTIONED = 90
# factor de extracción. Se multiplica el tamaño de la cola de tweets pendientes de enviar por este número
# para obtener el máximo de twitterusers que podemos extraer de cada proyecto
EXTRACTION_FACTOR = 30
# tiempo ventana a esperar por un extractor tras estar marcado como ratelimited
DEFAULT_RATELIMITED_TIMEWINDOW = 15  # en minutos


#
## FOLLOWER EXTRACTOR
#
EXTRACT_FOLLOWERS = True
TARGET_USER_PAGE_SIZE = 200

# para considerar twitterusers activos:
#   - máximo de días desde que el usuario se registró y todavía no envió ningún tweet
#   - máximo de días desde que el usuario twiteó por última vez
MAX_DAYS_SINCE_REGISTERED_ON_TWITTER_WITHOUT_TWEETS = 50
MAX_DAYS_SINCE_LAST_TWEET = 90

# máximo de páginas seguidas que el extractor toma de cada targetuser por extracción
MAX_CONSECUTIVE_PAGES_RETRIEVED_PER_TARGET_USER_EXTRACTION = 1

# en cada página extraída se espera como mínimo una x parte que sean twitterusers nuevos
TARGETUSER_EXTRACTION_MIN_NEW_TWITTERUSERS_PER_PAGE_EXPECTED = TARGET_USER_PAGE_SIZE/10
TARGETUSER_EXTRACTION_MAX_CONSECUTIVE_PAGES_RETRIEVED_WITHOUT_ENOUGH_NEW_TWITTERUSERS = 10

#
## HASHTAG EXTRACTOR
#
EXTRACT_HASHTAGS = False
# el extractor de hashtag paginará y se reiniciará cuando se cumpla alguna de las condiciones:
#   - el tweet más antiguo sea hace x o más minutos
#   - el número de usuarios es >= al máximo
HASHTAG_PAGE_SIZE = 100
FIRST_HASHTAG_ROUND_MAX_MINUTES_AGO_FOR_OLDER_TWEET = 60*6
FIRST_HASHTAG_ROUND_MAX_USER_COUNT = 10000
PER_HASHTAG_ROUND_MAX_USER_COUNT = 1000

# el tiempo que hay que esperar a la siguiente ronda
NEW_ROUND_TIMEWINDOW = 15*60  # en segundos

# máximo de páginas consecutivas a tomar por extracción sobre cada hashtag
MAX_CONSECUTIVE_PAGES_RETRIEVED_PER_HASHTAG_EXTRACTION = 10

# en cada página extraída esperamos un mínimo de twitterusers nuevos
HASHTAG_EXTRACTION_MIN_NEW_TWITTERUSERS_PER_PAGE_EXPECTED = HASHTAG_PAGE_SIZE/5
HASHTAG_EXTRACTION_MAX_CONSECUTIVE_PAGES_RETRIEVED_WITHOUT_ENOUGH_NEW_TWITTERUSERS = 5
HASHTAG_TIMEWINDOW_TO_WAIT_WHEN_NOT_ENOUGH_TWITTERUSERS = 30*60  # en segundos

#
# TWEET CREATOR
TIME_WAITING_FREE_QUEUE = 20  # cada x segundos se comprueba si hay espacio en la cola para crear nuevos tweets
TIME_WAITING_NEW_TWITTEABLE_BOTS = 120
MAX_UNMENTIONED_FETCHED_PER_PROJECT_LANG = 50
MAX_MENTIONS_PER_TWEET = 1
MAX_QUEUED_TWEETS_TO_SEND_PER_BOT = 50

#
# TWEET SENDER
MAX_THREADS_SENDING_TWEETS = 8  # máximo de hilos para enviar tweets
TOTAL_TASKS_SENDING_TWEETS = MAX_THREADS_SENDING_TWEETS  # número total de tareas para las hebras por cada vez que se ejecuta el proceso de enviar tweets
TIME_WAITING_NEXT_LOOKUP = 30
TIME_SLEEPING_AFTER_NO_BOTS_FOUND = 120  # tiempo que se duerme la hebra si no encuentra ningún bot disponible para lanzar tweet
TIME_SLEEPING_FOR_RESPAWN_TWEET_SENDER = 15

TWEET_LINK_LENGTH = 22
TWEET_IMG_LENGTH = 23

#
# MCTWEET VERIFICATION
REPLY_MSGS = {
    'all': [
        'lol',
        'omg',
        'omfg',
        'ok',
        'roflmao',
        'no',
    ],

    'en': [
        'dude',
        'thanks',
        'thx',
        'nice',
        'hah',
        'yes',
        'nope',
        'it rocks',
        'i like it',
        'bro',
        'bad',
        'good',
    ],

    'es': [
        'vale',
        'bueno',
        'tio',
        'gracias',
        'claro',
        'si',
        'me gusta',
        'entiendo',
    ],
}

#
# BOT CREATOR
MAX_THREADS_CREATING_BOTS = 8  # máximo de hilos para crear bots
BIRTH_INTERVAL = (1975, 1995)  # intervalo para elegir aleatoriamente la fecha de nacimiento del bot
EMAIL_ACCOUNT_TYPE = 'hotmail.com'
REGISTER_EMAIL = True  # para activar o no el registro del email
TW_CONFIRM_EMAIL = True  # para activar o no el leer el email de confirmación de twitter
TW_SET_PROFILE = True
TW_SET_AVATAR = True
TW_SET_BIO = True
# si no activamos registro de email evidentemente no haremos la confirmación
if not REGISTER_EMAIL:
    TW_CONFIRM_EMAIL = False
if not TW_SET_PROFILE:
    TW_SET_AVATAR = False
    TW_SET_BIO = False
TIME_SLEEPING_FOR_RESPAWN_BOT_CREATOR = 120
REUSE_PROXIES_REQUIRING_PHONE_VERIFICATION = False
PRIORIZE_RUNNING_PROJECTS_FOR_BOT_CREATION = True

NEW_BOTS_FILES_DIR = os.path.join(PROJECT_ROOT, 'core', 'bots')
NEW_BOTS_NO_PROFILE_FILE = os.path.join(NEW_BOTS_FILES_DIR, 'no_profile.csv')
NEW_BOTS_PROFILED_FILE = os.path.join(NEW_BOTS_FILES_DIR, 'profiled.csv')
NEW_BOTS_PHONE_VERIFIED_FILE = os.path.join(NEW_BOTS_FILES_DIR, 'phone_verified.csv')


#
# BOT CREATION FINISHER
MAX_THREADS_COMPLETING_PENDANT_BOTS = 40  # máximo de hilos para restaurar creación de robots todavía a medias
TIME_SLEEPING_FOR_RESPAWN_BOT_CREATION_FINISHER = 60 * 15
MARK_BOT_AS_DEATH_AFTER_TRYING_LIFTING_SUSPENSION = False

MARK_PROXIES_AS_UNAVAILABLE_FOR_USE = True

#
# PATHS
SCRAPPER_PATH = os.path.join(PROJECT_ROOT, 'core', 'scrapper')
WEBDRIVERS_PATH = os.path.join(SCRAPPER_PATH, 'webdrivers')

CASPERJS_SCRIPTS_PATH = os.path.join(SCRAPPER_PATH, 'casper_scripts')

PHANTOMJS_PATH = os.path.join(WEBDRIVERS_PATH, 'phantomjs')

# PHANTOMJS BIN
if sys.platform == "win32":
    PHANTOMJS_BIN_PATH = os.path.join(PHANTOMJS_PATH, 'phantomjs_windows_bin.exe')
elif sys.platform == 'linux2':
    PHANTOMJS_BIN_PATH = os.path.join(PHANTOMJS_PATH, 'phantomjs_dev_linux_bin')
else:
    PHANTOMJS_BIN_PATH = os.path.join(PHANTOMJS_PATH, 'phantomjs_mac_bin_1_9_8')

CASPERJS_BIN_PATH = '/opt/casperjs/bin/casperjs'

# PHANTOMJS COOKIES
PHANTOMJS_COOKIES_DIR = os.path.join(PHANTOMJS_PATH, 'cookies')

SCREENSHOTS_DIR = os.path.join(SCRAPPER_PATH, 'screenshots')
CASPERJS_SCREENSHOTS_DIR = os.path.join(SCRAPPER_PATH, 'casper_screenshots')
AVATARS_DIR = os.path.join(SCRAPPER_PATH, 'avatars')
CAPTCHAS_DIR = os.path.join(SCRAPPER_PATH, 'captchas')
PROXIES_DIR = os.path.join(PROJECT_ROOT, 'core', 'proxies')
# by default in /Users/<User>/Library/Application Support/Ofi Labs/PhantomJS
# PHANTOMJS_LOCALSTORAGES_PATH = os.path.join(PHANTOMJS_PATH, 'localstorages')


# FI (firefox)
# CH (chrome)
# PH (phantomjs)
# WEBDRIVER = 'FI'