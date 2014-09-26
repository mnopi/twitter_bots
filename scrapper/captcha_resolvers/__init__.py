# -*- coding: utf-8 -*-

import os
from PIL import Image
import requests
import simplejson
import time
from scrapper import settings
from scrapper.captcha_resolvers import deathbycaptcha
from scrapper.logger import LOGGER


DEFAULT_TIMEOUT = 30
POLL_INTERVAL = 5


class CaptchaResolver(object):
    def __init__(self, scrapper):
        self.scrapper = scrapper

    def crop_captcha(self, img_el, captcha_filename):
        # puesto que no se puede sacar una url para ese captcha y bajar de ahí la imágen
        # se realiza una captura de pantalla para luego recortarla justo por donde queda el captcha
        location = img_el.location
        size = img_el.size

        self.scrapper.browser.save_screenshot(captcha_filename) # saves screenshot of entire page
        im = Image.open(captcha_filename) # uses PIL library to open image in memory

        left = location['x']
        top = location['y']
        right = location['x'] + size['width']
        bottom = location['y'] + size['height']

        im = im.crop((left, top, right, bottom)) # defines crop points
        im.save(captcha_filename) # saves new cropped image


class DeathByCaptchaResolver(CaptchaResolver):
    def resolve_captcha(self, img_el=None, sol_el=None, captcha_filename=None, timeout=None):
        def upload_captcha():
            def poll_captcha(captcha_id):
                r = requests.get('http://api.dbcapi.me/api/captcha/%i' % captcha_id, headers={'accept': 'application/json'})
                return simplejson.loads(r.content)

            r = None
            try:
                files = {
                    'username': settings.DEATHBYCAPTCHA_USER,
                    'password': settings.DEATHBYCAPTCHA_PASSWORD,
                    'captchafile': open(captcha_filename, 'rb')
                }
                r = requests.post('http://api.dbcapi.me/api/captcha',
                                  files=files, headers={'Accept': 'application/json'})
                resp = simplejson.loads(r.content)

                if resp['captcha']:
                    deadline = time.time() + (max(0, timeout) or DEFAULT_TIMEOUT)
                    uploaded_captcha = simplejson.loads(r.content)
                    if uploaded_captcha:
                        while deadline > time.time() and not uploaded_captcha['text']:
                            time.sleep(POLL_INTERVAL)
                            pulled = poll_captcha(uploaded_captcha['captcha'])
                            if pulled['captcha'] == uploaded_captcha['captcha']:
                                uploaded_captcha = pulled
                        if uploaded_captcha['text'] and uploaded_captcha['is_correct']:
                            self.scrapper.captcha_res = uploaded_captcha
            except Exception:
                settings.LOGGER.exception('Failed uploading CAPTCHA, response:\n\t%s' % r.content)
                self.scrapper.captcha_res = None
                raise

            os.remove(captcha_filename)  # borramos del disco duro la foto que teníamos del captcha

        if type(img_el) is str:
            img_el = self.scrapper.get_css_element(img_el)
        if type(sol_el) is str:
            sol_el = self.scrapper.get_css_element(sol_el)

        # movemos cursor hasta el campo de texto del captcha y hacemos click en él para que la captura salga bien
        self.scrapper.click(sol_el)

        captcha_filename = captcha_filename if captcha_filename else self.scrapper.user.username + '_captcha.png'
        self.crop_captcha(img_el, captcha_filename)
        upload_captcha()

        if self.scrapper.captcha_res:
            self.scrapper.fill_input_text(sol_el, self.scrapper.captcha_res['text'])

    def report_wrong_captcha(self):
        try:
            client = deathbycaptcha.SocketClient(settings.DEATHBYCAPTCHA_USER, settings.DEATHBYCAPTCHA_PASSWORD)
            client.report(self.scrapper.captcha_res['captcha'])
        except Exception, e:
            LOGGER.exception('Failed reporting wrong CAPTCHA')


    # usando la api de esta gente no funciona..

    # def resolve_captcha(self, img_el=None, sol_el=None, captcha_filename=None):
    #     def upload_captcha():
    #         client = deathbycaptcha.SocketClient(settings.DEATHBYCAPTCHA_USER, settings.DEATHBYCAPTCHA_PASSWORD)
    #         try:
    #             # Put your CAPTCHA image file name or file-like object, and optional
    #             # solving timeout (in seconds) here:
    #             self.scrapper.captcha_res = client.decode(captcha_filename)
    #         except Exception:
    #             LOGGER.exception('Failed uploading CAPTCHA')
    #             self.scrapper.captcha_res = None
    #
    #         os.remove(captcha_filename)  # borramos del disco duro la foto que teníamos del captcha
    #
    #     captcha_filename = captcha_filename if captcha_filename else self.scrapper.user.username + '_captcha.png'
    #     self.crop_captcha(img_el, captcha_filename)
    #     upload_captcha()
    #
    #     if self.scrapper.captcha_res:
    #         send_keys(sol_el, self.scrapper.captcha_res['text'])
    #
    # def report_wrong_captcha(self):
    #     try:
    #         client = deathbycaptcha.SocketClient(settings.DEATHBYCAPTCHA_USER, settings.DEATHBYCAPTCHA_PASSWORD)
    #         client.report(self.scrapper.captcha_res['captcha'])
    #     except Exception, e:
    #         LOGGER.exception('Failed reporting wrong CAPTCHA')