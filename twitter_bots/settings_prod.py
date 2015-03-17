import socket
from settings import *
import settings
import os


#
# django settings
settings.PROD_MODE = True
DEBUG = settings.TEMPLATE_DEBUG = True
ALLOWED_HOSTS = ['localhost', '88.26.212.82', '192.168.1.115']

DATABASE_HOST = 'localhost' if socket.gethostname() == 'p1' else '88.26.212.82'
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "twitter_bots_prod",
        "USER": "root",
        "PASSWORD": "1aragon1",
        "HOST": DATABASE_HOST,
        "PORT": "3306",
    }
}

#
# scrapping settings
settings.PHANTOMJS_BIN_PATH = os.path.join(PHANTOMJS_PATH, 'phantomjs_prod_linux_bin')

settings.MAX_THREADS_COMPLETING_PENDANT_BOTS = 50
settings.MAX_THREADS_CREATING_BOTS = 70
settings.MAX_PROCESSES_SENDING_TWEETS = 50
settings.TOTAL_TASKS_SENDING_TWEETS = settings.MAX_PROCESSES_SENDING_TWEETS * 10
settings.TAKE_SCREENSHOTS = False





