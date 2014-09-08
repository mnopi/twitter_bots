# -*- coding: utf-8 -*-

from scrapper import Scrapper
from scrapper.utils import *
import logging

LOGGER = logging.getLogger(__name__)

class HushmailScrapper(Scrapper):
    def sign_up(self):
        try:
            self.open_browser()
            self.browser.get(settings.URLS['hushmail_reg'])
            send_keys(self.browser.find_element_by_id('hush_username'), self.user.get_email_username())
            send_keys(self.browser.find_element_by_id('hush_pass1'), self.user.password_email)
            send_keys(self.browser.find_element_by_id('hush_pass2'), self.user.password_email)
            self.resolve_captcha(
                self.browser.find_element_by_id('verificationImage'),
                self.browser.find_element_by_id('hush_turing_response')
            )
            click(self.browser.find_element_by_id('hush_tos'))
            click(self.browser.find_element_by_id('hush_additional_tos'))
            click(self.browser.find_element_by_id('createKeysButton'))

            if check_condition(lambda: "Enter payment information" in self.browser.title, timeout=15):
                self.user.email_registered_ok = True
                self.user.save()
                LOGGER.info('%s registrado correctamente' % self.user.email)
            else:
                if self.check_visibility('.hushform_newaccountform_hush_turing_response .HushmailInlineError'):
                    # captcha mal puesto, se reporta
                    self.report_wrong_captcha()
                raise
        except Exception:
            LOGGER.exception('Could not register email %s' % (self.user.email))
            raise

    def login(self):
        self.open_browser()
        self.browser.get(settings.URLS['hushmail_login'])
        create_delay()
        send_keys(self.browser.find_element_by_id('hush_username'), self.user.get_email_username())
        send_keys(self.browser.find_element_by_id('hush_passphrase'), self.user.password_email)
        click(self.browser.find_element_by_css_selector('#submit-container input'))
        create_delay(seconds=7.0)

    def confirm_tw_email(self):
        self.login()

        # número de ventanas que tenemos abiertas antes de abrir la de la confirmación de twitter
        self.num_prev_opened_windows = len(self.browser.window_handles)

        # click sobre la cajita en bandeja de entrada correspondiente al mensaje recibido por twitter
        click(self.get_css_element("#element_message-list-table tr td.subject a.read-message"))

        # nos movemos al iframe dentro del mensaje y una vez dentro hacemos click en el link de confirmación
        email_msg_iframe = self.get_css_element('#message').find_element_by_css_selector('iframe')
        self.browser.switch_to.frame(email_msg_iframe)
        click(self.browser.find_element_by_css_selector('a.button_link'))

        # al haber hecho click se abre una ventana nueva con la confirmación en twitter. Esperamos a que
        # su contenido se cargue por completo y luego metemos un retardo
        wait_condition(self.twitter_page_is_loaded_on_new_window)
        create_delay(5)