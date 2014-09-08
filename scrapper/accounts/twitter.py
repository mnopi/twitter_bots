# -*- coding: utf-8 -*-
import os

from scrapper import Scrapper, INVALID_EMAIL_DOMAIN_MSG, LOGGER
from scrapper.captcha_resolvers import DeathByCaptchaResolver
from scrapper.exceptions import TwitterEmailNotFound
from scrapper.utils import *
from scrapper import settings
from scrapper import delay


class TwitterScrapper(Scrapper):
    PHANTOMJS_SCREENSHOTS_SCRAPPER_FOLDER = 'twitter'

    def sign_up(self):
        """Crea una cuenta de twitter con los datos dados. No guarda nada en BD, sólo entra en twitter y lo registra"""

        def submit_form(chg_username_attempts=0):
            """Hace click en submit, mira si hay errores corrigiéndolos. si los hay vuelta a empezar.."""
            def check_form():
                errors = False
                # email puede que esté disponible al registrar pero luego twitter diga que nanai..
                if self.check_visibility('.prompt.email p.error.active'):
                    errors = True
                    fucked_email = self.user.email
                    self.user.email_registered_ok = False
                    self.user.save()
                    raise Exception('Email %s exists on twitter' % fucked_email)

                # username
                if self.check_visibility('.select-username .sidetip .error.active'):
                    errors = True
                    if chg_username_attempts <= 5:
                        self.user.username = generate_random_username(self.user.real_name)
                        self.fill_input_text('#username', self.user.username)
                        #send_keys(self.browser.find_element_by_id('username'), self.user.username)
                    else:
                        alternatives = self.get_css_element('.suggestions button')
                        alt = random.choice(alternatives)
                        self.username = alt.text
                        self.click(alt)

                return errors

            # CLICK ON SUBMIT
            delay.seconds(7)
            self.click('input[name="submit_button"]')
            LOGGER.info('User %s hit submit button for sign up twitter (attempt %i)' % (self.user, chg_username_attempts))

            errors = check_form()
            if errors:
                submit_form(chg_username_attempts+1)

            # if not check_condition(lambda: 'welcome' in self.browser.current_url,
            #                        err_msg='User %s cannot register on twitter' % self.user.username):
            #     submit_form(chg_username_attempts+1)

        try:
            LOGGER.info('User %s signing up on twitter..' % self.user.username)
            if self.user.has_to_register_twitter():
                self.open_browser()
                self.go_to(settings.URLS['twitter_reg'])
                # esperamos a que se cargue bien el formulario
                self.wait_visibility_of_css_element('#full-name', timeout=15)

                # rellenamos
                self.fill_input_text('#full-name', self.user.real_name)
                self.fill_input_text('#email', self.user.email)
                self.fill_input_text('#password', self.user.password_twitter)
                self.fill_input_text('#username', self.user.username)
                submit_form()
                delay.seconds(10)

                # finalmente lo ponemos como registrado en twitter
                self.user.twitter_registered_ok = True
                self.user.save()

                # le damos al botón 'next' que sale en la bienvenida
                welcome_a = 'a[href="/welcome/recommendations"]'
                if self.check_visibility(welcome_a):
                    self.click(welcome_a)

                self.wait_to_page_loaded()
                delay.seconds(7)

                # comprobamos que la cuenta de twitter está operativa
                #self.check_twitter_signup_ok()
                LOGGER.info('User %s successfully signed up on twitter' % self.user.username)
        except Exception, e:
            LOGGER.exception('User %s has errors signing up twitter account' % self.user.username)
            raise e

    def check_twitter_signup_ok(self):
        self.login()

    def login(self):
        try:
            self.open_browser()
            self.go_to(settings.URLS['twitter_login'])
            self.click('.remember-forgot input')
            self.fill_input_text('#signin-email', self.user.username)
            self.fill_input_text('#signin-password', self.user.password_twitter)
            self.click('.front-signin button')
            self.wait_to_page_loaded()

            # comprobamos que no esté suspendida la cuenta
            if self.check_visibility('#account-suspended'):
                cr = DeathByCaptchaResolver(self)

                def submit_unsuspension():
                    cr.resolve_captcha(
                        self.get_css_element('#recaptcha_challenge_image'),
                        self.get_css_element('#recaptcha_response_field')
                    )
                    self.click('#suspended_help_submit')
                    delay.seconds(5)

                    if self.check_visibility('form.t1-form .error-occurred'):
                        cr.report_wrong_captcha()
                        submit_unsuspension()

                self.user.mark_as_suspended()
                self.click(self.get_css_element('#account-suspended a'))
                self.click('#checkbox_discontinue')
                self.click('#checkbox_permanent')
                submit_unsuspension()
            elif self.check_visibility('button.resend-confirmation-email-link'):
                self.click('button.resend-confirmation-email-link')
                delay.seconds(2)
            else:
                user_not_found_el = get_element(lambda: self.get_css_element('#message-drawer'))
                if user_not_found_el and 'The username and password you entered did not match our records' in user_not_found_el.text:
                    # si el usuario no se encuentra
                    self.user.mark_as_not_twitter_registered_ok()
                else:
                    # si el usuario se encuentra..
                    self.user.it_works = True
                    self.user.save()
        except Exception, e:
            LOGGER.exception('Login on twitter error for %s' % self.user.username)
            raise e

    def check_account_suspended(self):
        """Una vez intentado el logueo miramos si fue suspendida la cuenta"""
        def bot_is_suspended():
            try:
                is_suspended = self.browser.find_element_by_id('account-suspended').is_displayed()
            except Exception:
                is_suspended = 'error' in self.browser.current_url
            return is_suspended

        try:
            self.login()
            if check_condition(bot_is_suspended):
                self.user.mark_as_suspended()
                self.close_browser()
            elif check_condition(lambda: 'locked' in self.browser.current_url):
                # en el caso de problemas con el proxy actual porque le hayan detectado muchas peticiones
                # de login seguidas, en ese caso se vuelve a comprobar el bot con otra ip
                self.check_account_suspended()
            else:
                # si el usuario está 'sanote' cerramos navegador sin hacer nada
                self.close_browser()
        except Exception:
            # si ha habido algún otro problema volvemos a comprobar el usuario
            LOGGER.exception('Problem checking if twitter account was suspended for "%s"' % self.user.username)
            self.check_account_suspended()

    def twitter_page_is_loaded_on_new_window(self):
        """mira si se cargó por completo la página en la ventana nueva que se abre al pinchar en el enlace
        del email de confirmación enviado por twitter"""
        is_twitter_confirm_window_opened = len(self.browser.window_handles) == self.num_prev_opened_windows + 1
        if is_twitter_confirm_window_opened:
            self.switch_to_window(-1)
            return self.browser.execute_script("return document.readyState;") == 'complete'
        else:
            return False

    def confirm_user_email(self):
        """Le damos al rollo del email de confirmación.."""
        try:
            LOGGER.info('Confirming email %s for twitter user: %s..' % (self.user.email, self.user.username))
            if self.user.has_to_confirm_tw_email():
                from scrapper.accounts.gmail import GmailScrapper
                from scrapper.accounts.hotmail import HotmailScrapper
                from scrapper.accounts.hushmail import HushmailScrapper

                email_domain = self.user.get_email_account_domain()
                if email_domain == 'hushmail.com':
                    self.email_scrapper = HushmailScrapper(self.user)
                elif email_domain == 'gmail.com':
                    self.email_scrapper = GmailScrapper(self.user)
                elif email_domain == 'hotmail.com' or email_domain == 'outlook.com':
                    self.email_scrapper = HotmailScrapper(self.user)
                else:
                    raise Exception(INVALID_EMAIL_DOMAIN_MSG)

                self.email_scrapper.open_browser()
                self.email_scrapper.confirm_tw_email()
                self.email_scrapper.close_browser()
                self.user.twitter_confirmed_email_ok = True
                self.user.save()
                LOGGER.info('Twitter email confirmed ok for %s with email: %s' % (self.user.username, self.user.email))
        except TwitterEmailNotFound:
            self.login()
            self.confirm_user_email()
        except Exception, e:
            LOGGER.exception('Error confirming twitter email. User: %s, email: %s' %(self.user.username, self.user.email))
            raise e

    def set_profile(self):
        """precondición: estar logueado y en la home"""
        def set_avatar():
            if self.check_visibility('div.ProfileAvatar > a'):
                self.click('div.ProfileAvatar > a')
                upload_btn = '#photo-choose-existing input[type="file"]'
                self.download_pic_from_google()

                avatar_path = os.path.join(settings.PROJECT_ROOT, 'avatars', '%s.png' % self.user.username)
                self.get_css_element(upload_btn).send_keys(avatar_path)
                self.click('#profile_image_upload_dialog-dialog button.profile-image-save')
                # eliminamos el archivo que habíamos guardado para el avatar
                os.remove(avatar_path)

        def set_bio():
            self.fill_input_text('#user_description', self.get_quote())

        self.click('a.DashboardProfileCard-avatarLink')
        self.click('button.UserActions-editButton')
        delay.seconds(3)
        set_avatar()
        set_bio()
        self.click('.ProfilePage-editingButtons button.ProfilePage-saveButton')