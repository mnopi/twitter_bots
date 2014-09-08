# -*- coding: utf-8 -*-

from scrapper import Scrapper
from scrapper.utils import *
import logging

LOGGER = logging.getLogger(__name__)

class GmailScrapper(Scrapper):
    def sign_up(self):
        def submit_form():
            """Comprobamos que todo bien y enviamos registro. Si no sale bien corregimos y volvemos a enviar,
            y así sucesivamente"""
            if self.check_visibility('#GmailAddress.form-error'):
                suggestions = self.browser.find_elements_by_css_selector('#username-suggestions a')
                if suggestions:
                    click(random.choice(suggestions))
                else:
                    self.user.email = generate_random_username(self.user.real_name) + '@gmail.com'
                    send_keys(self.browser.find_element_by_id('GmailAddress'), self.user.email.split('@')[0])


            if self.check_visibility('#errormsg_0_signupcaptcha'):
                self.report_wrong_captcha()
                self.resolve_captcha(
                    self.browser.find_element_by_css_selector('#recaptcha_image'),
                    self.browser.find_element_by_css_selector('#recaptcha_response_field')
                )

            if self.check_visibility('#Passwd.form-error'):
                send_keys(self.browser.find_element_by_id('Passwd'), self.user.password_email)
                send_keys(self.browser.find_element_by_id('PasswdAgain'), self.user.password_email)

            click(self.browser.find_element_by_css_selector('#submitbutton'))

            if self.check_visibility('#GmailAddress.form-error') or \
                self.check_visibility('#errormsg_0_signupcaptcha') or \
                self.check_visibility('#Passwd.form-error'):
                submit_form()

        self.browser.get(settings.URLS['gmail_reg'])
        first_name, last_name = self.user.real_name.split(' ')

        send_keys(self.browser.find_element_by_id('FirstName'), first_name)
        send_keys(self.browser.find_element_by_id('LastName'), last_name)
        send_keys(self.browser.find_element_by_id('GmailAddress'), self.user.email.split('@')[0])
        send_keys(self.browser.find_element_by_id('Passwd'), self.user.password_email)
        send_keys(self.browser.find_element_by_id('PasswdAgain'), self.user.password_email)

        # cumpleaños
        # dia
        send_keys(self.browser.find_element_by_id('BirthDay'), str(self.user.birth_date.day))
        # mes
        click(self.browser.find_element_by_css_selector('#BirthMonth div'))
        self.browser.find_elements_by_css_selector('#BirthMonth div.goog-menu > div')[self.user.birth_date.month-1].click()
        # año
        send_keys(self.browser.find_element_by_id('BirthYear'), str(self.user.birth_date.year))

        # sexo
        click(self.browser.find_element_by_css_selector('#Gender div'))
        i = 0 if self.user.gender == 1 else 1
        click(self.browser.find_elements_by_css_selector('#Gender div.goog-menu > div')[self.gender+i])

        # captcha
        self.resolve_captcha(
            self.browser.find_element_by_css_selector('#recaptcha_image'),
            self.browser.find_element_by_css_selector('#recaptcha_response_field')
        )

        click(self.browser.find_element_by_css_selector('#TermsOfService'))
        submit_form()

    def login(self):
        raise NotImplementedError

    def confirm_tw_email(self):
        """Al llegar a este punto se supone que ya nos habemos logueado previamente en nuestra cuenta gmail"""
        raise NotImplementedError
