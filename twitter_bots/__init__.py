# -*- coding: utf-8 -*-

# creamos estas carpetas si no existen, ya que las hemos añadido al gitignore
from scrapper.utils import mkdir_if_not_exists
from twitter_bots.settings import SCREENSHOTS_DIR, AVATARS_DIR, PHANTOMJS_COOKIES_DIR, LOGS_DIR, SUPERVISOR_LOGS_DIR

mkdir_if_not_exists(SCREENSHOTS_DIR)
mkdir_if_not_exists(AVATARS_DIR)
mkdir_if_not_exists(PHANTOMJS_COOKIES_DIR)
mkdir_if_not_exists(LOGS_DIR)
mkdir_if_not_exists(SUPERVISOR_LOGS_DIR)