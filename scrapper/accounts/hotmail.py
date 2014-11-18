# -*- coding: utf-8 -*-
from selenium.webdriver.common.keys import Keys

from scrapper.scrapper import Scrapper
from scrapper.captcha_resolvers import DeathByCaptchaResolver
from scrapper.exceptions import TwitterEmailNotFound, EmailAccountSuspended
from scrapper.utils import *
from twitter_bots import settings


class HotmailScrapper(Scrapper):

    def sign_up(self):
        def resolve_captcha():
            captcha_resolver.resolve_captcha(
                self.browser.find_elements_by_css_selector('#iHipHolder img')[0],
                self.get_css_element('#iHipHolder input.hipInputText')
            )

        def fix_username(errors=False):
            # username
            if self.check_visibility('#iPwd'):
                self.click('#iPwd')
            if self.check_visibility('#iMembernameLiveError', timeout=5) or \
                    self.check_visibility('#iLiveMessageError'):
                self.take_screenshot('form_wrong_username')
                errors = True
                if self.check_visibility('#sug'):
                    suggestions = self.get_css_elements('#sug #mysugs div a', timeout=10)
                    chosen_suggestion = random.choice(suggestions)
                    self.user.email = chosen_suggestion.text
                    self.click(chosen_suggestion)
                else:
                    self.user.email = generate_random_username(self.user.real_name) + '@hotmail.com'
                    self.fill_input_text('#imembernamelive', self.user.get_email_username())
                    self.delay.seconds(5)
                fix_username(errors)
            else:
                pass

        def submit_form():
            """Comprobamos que todo bien y enviamos registro. Si no sale bien corregimos y volvemos a enviar,
            y así sucesivamente"""

            def check_form():
                errors = False
                self.take_screenshot('checking_form_after_submit')

                self.delay.seconds(7)  # todo: comprobar después de captcha
                fix_username(errors)

                # error en passwords
                if self.check_visibility('#iPwdError'):
                    errors = True
                    self.user.password_email = generate_random_string()
                    self.fill_input_text('#iPwd', self.user.password_email)
                    self.fill_input_text('#iRetypePwd', self.user.password_email)

                # error en captcha
                captcha_errors = self.get_css_elements('.hipErrorText')
                captcha_error_visible = captcha_errors and \
                                        (
                                            self.check_visibility(captcha_errors[1], timeout=5) or
                                            self.check_visibility(captcha_errors[2], timeout=5)
                                        )
                if captcha_error_visible:
                    self.click('#iHipHolder input.hipInputText')
                    self.take_screenshot('form_wrong_captcha', force_take=True)
                    errors = True
                    #captcha_resolver.report_wrong_captcha()
                    resolve_captcha()

                return errors

            self.click('#createbuttons input')

            errors = check_form()
            if errors:
                submit_form()

        def fill_form():
            self.click('#iliveswitch')
            self.fill_input_text('#iFirstName', self.user.real_name.split(' ')[0])
            self.fill_input_text('#iLastName', self.user.real_name.split(' ')[1])

            # cambiamos de @outlok a hotmail
            self.click('#idomain')
            self.send_special_key(Keys.ARROW_DOWN)
            self.send_special_key(Keys.ENTER)

            # username (lo que va antes del @)
            self.fill_input_text('#imembernamelive', self.user.get_email_username())

            # provocamos click en pwd para que salte lo de apañar el nombre de usuario
            fix_username()

            # una vez corregido el nombre de usuario seguimos rellenando el password y demás..
            self.fill_input_text('#iPwd', self.user.password_email)
            self.fill_input_text('#iRetypePwd', self.user.password_email)
            self.fill_input_text('#iZipCode', self.get_usa_zip_code())

            # FECHA DE NACIMIENTO
            self.click('#iBirthMonth')
            for _ in range(0, self.user.birth_date.month):
                self.send_special_key(Keys.ARROW_DOWN)
            self.delay.seconds(1, force_delay=True)
            self.fill_input_text('#iBirthDay', self.user.birth_date.day)
            self.delay.seconds(1, force_delay=True)
            self.fill_input_text('#iBirthYear', self.user.birth_date.year)

            # SEXO
            self.click('#iGender')
            for _ in range(0, self.user.gender+1):
                self.send_special_key(Keys.ARROW_DOWN)

            self.fill_input_text('#iAltEmail', generate_random_username() + '@gmail.com')

            resolve_captcha()

            self.click('#iOptinEmail')

        settings.LOGGER.info('Signing up %s..' % self.user.email)
        self.go_to(settings.URLS['hotmail_reg'])
        captcha_resolver = DeathByCaptchaResolver(self)
        self.wait_visibility_of_css_element('#iliveswitch', timeout=10)
        fill_form()
        self.delay.seconds(5)
        submit_form()
        if not self.check_visibility('#meControlHeader', timeout=60):
            raise Exception()
        # wait_condition(lambda: 'welcome' in self.get_css_element('#overview-head h2').text.lower(), timeout=60)

    def check_account_suspended(self):
        not_suspended = lambda: 'unblock' not in self.browser.title.lower()
        suspended = not check_condition(not_suspended)
        if suspended:
            raise EmailAccountSuspended(self.user)

    def login(self):
        def submit_form(attempts=0):
            def check_form():
                errors = False

                if self.check_visibility('#idTd_Tile_ErrorMsg_Login', timeout=10):
                    errors = True

                    if self.check_visibility('#idTd_HIP_HIPControl'):
                        # si hay captcha que rellenar..
                        cr = DeathByCaptchaResolver(self)
                        cr.resolve_captcha('#idTd_HIP_HIPControl img', '#idTd_HIP_HIPControl input')
                        self.fill_input_text('input[name=passwd]', self.user.password_email)
                    else:
                        # si no hay captcha entonces lo damos por email malo y lanzamos excepción
                        self.user.email_registered_ok = False
                        self.user.save()
                        self.take_screenshot('wrong_email_account_for_login')
                        self.close_browser()
                        raise Exception()
                return errors

            if attempts > 1:
                self.user.email_registered_ok = False
                self.user.save()
                self.take_screenshot('too_many_attempts')
                self.close_browser()
                raise Exception('too many attempts to login %s' % self.user.email)

            self.click('input[type="submit"]')
            errors = check_form()
            if errors:
                submit_form(attempts+1)

        try:
            self.go_to(settings.URLS['hotmail_login'])
            if self.check_visibility('#idDiv_PWD_UsernameTb'):
                self.fill_input_text('#idDiv_PWD_UsernameTb input', self.user.email)
                self.fill_input_text('#idDiv_PWD_PasswordTb input', self.user.password_email)
                self.click('#idChkBx_PWD_KMSI0Pwd')  # para mantener la sesión si cierro navegador
                submit_form()
                self.wait_to_page_loaded()
            self._quit_inbox_shit()
            self.check_account_suspended()
            settings.LOGGER.info('User %s logged in hotmail' % self.user.email)
        except Exception as ex:
            settings.LOGGER.exception('The was a problem loggin in %s' % self.user.email)
            raise ex

    def _quit_inbox_shit(self):
        # en el caso de aparecer esto tras el login le damos al enlace que aparece en la página
        if check_condition(lambda: 'BrowserSupport' in self.browser.current_url):
            self.take_screenshot('continue_to_your_inbox_link')
            self.browser.find_element_by_partial_link_text('continue to your inbox').click()

        # si nos salta el mensaje de bienvenida
        self.wait_to_page_loaded()
        if self.check_visibility('#notificationContainer button', timeout=10):
            self.click('#notificationContainer button')

    def confirm_tw_email(self):
        self.login()

        # vemos si realmente estamos en la bandeja de entrada
        if not self.check_visibility('#pageInbox'):
            self.take_screenshot('not_really_on_inbox_page')
            raise Exception('%s is not really on inbox page after login' % self.user.email)

        twitter_email_title = get_element(lambda: self.browser.find_element_by_partial_link_text('Twitter account'))
        if twitter_email_title:
            self.click(twitter_email_title)
            self.wait_to_page_loaded()
            confirm_btn = get_element(lambda: self.browser.find_element_by_partial_link_text('Confirm'))
            self.click(confirm_btn)
            self.delay.seconds(3)
            self.switch_to_window(-1)
            self.wait_to_page_loaded()
            self.delay.seconds(3)

            # por si nos pide meter usuario y contraseña
            if not self.check_visibility('#global-new-tweet-button'):
                self.send_keys(self.user.username)
                self.send_special_key(Keys.TAB)
                self.send_keys(self.user.password_twitter)
                self.send_special_key(Keys.ENTER)
                self.delay.seconds(7)
        else:
            settings.LOGGER.warning('No twitter email arrived for user %s, resending twitter email..' % self.user.username)
            raise TwitterEmailNotFound()