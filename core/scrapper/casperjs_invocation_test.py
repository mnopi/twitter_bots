# -*- coding: utf-8 -*-

import os
import subprocess
import settings

CASPER = '/home/robots/casperjs/bin/casperjs'
SCRAPPER_DIR = os.path.join(settings.PROJECT_ROOT, 'core', 'scrapper')
SCRIPT = os.path.join(SCRAPPER_DIR, 'casper_scripts', 'myip.js')
CASPER_SCREENSHOTS_DIR = os.path.join(SCRAPPER_DIR, 'casper_screenshots')

params = CASPER + ' ' + SCRIPT \
         + ' ' + '--screenshots=%s' % CASPER_SCREENSHOTS_DIR\
         + ' ' + '--id="%d ningún coño másss"' % 4


o = subprocess.check_output(params, shell=True)
pass