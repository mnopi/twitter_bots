# -*- coding: utf-8 -*-
import os
from selenium.common.exceptions import MoveTargetOutOfBoundsException
from selenium.webdriver.common.keys import Keys

from scrapper.scrapper import Scrapper, INVALID_EMAIL_DOMAIN_MSG, LOGGER
from scrapper.captcha_resolvers import DeathByCaptchaResolver
from scrapper.exceptions import TwitterEmailNotFound, BotDetectedAsSpammerException
from scrapper.utils import *
from twitter_bots import settings
from scrapper import delay


class TwitterScrapper(Scrapper):
    SCREENSHOTS_DIR = 'twitter'

    def sign_up(self):
        """Crea una cuenta de twitter con los datos dados. No guarda nada en BD, sólo entra en twitter y lo registra"""

        def check_email():
            while True:
                if self.check_visibility('.prompt.email .sidetip .checking.active'):
                    self.delay.seconds(0.5, force_delay=True)
                elif self.check_visibility('.prompt.email .sidetip .error.active'):
                    if self.user.is_kamikaze:
                        self.user.generate_email()
                        self.user.save()
                        self.fill_input_text('#email', self.user.email)
                    else:
                        fucked_email = self.user.email
                        self.user.email_registered_ok = False
                        self.user.save()
                        raise Exception('Email %s exists on twitter' % fucked_email)
                elif self.check_visibility('.prompt.email .sidetip .ok.active'):
                    break

            # while self.check_visibility('.prompt.email .sidetip .error.active', timeout=5):
            #     if self.user.is_kamikaze:
            #         self.user.email = generate_random_username(self.user.real_name) + '@hotmail.com'
            #         self.user.save()
            #         self.fill_input_text('#email', self.user.email)
            #     else:
            #         fucked_email = self.user.email
            #         self.user.email_registered_ok = False
            #         self.user.save()
            #         raise Exception('Email %s exists on twitter' % fucked_email)

        def check_username():
            while True:
                # CHECKING..
                if self.check_visibility('.select-username .sidetip .checking.active'):
                    self.delay.seconds(0.5, force_delay=True)
                # ERROR
                elif self.check_visibility('.select-username .sidetip .error.active'):
                    alternatives = self.get_css_elements('.suggestions button')
                    if alternatives:
                        # puede que alguna alternativa no se vea, así que si va mal el click cogemos otra hasta que vaya
                        while True:
                            alt = random.choice(alternatives)
                            self.username = alt.text
                            try:
                                self.click(alt)
                                break
                            except MoveTargetOutOfBoundsException:
                                pass
                    else:
                        self.user.username = generate_random_username(self.user.real_name)
                        self.fill_input_text('#username', self.user.username)
                # USERNAME OK
                elif self.check_visibility('.select-username .sidetip .ok.active'):
                    break

            # while self.check_visibility('.select-username .sidetip .error.active', timeout=5):
            #     alternatives = self.get_css_elements('.suggestions button')
            #     if alternatives:
            #         # puede que alguna alternativa no se vea, así que si va mal el click cogemos otra hasta que vaya
            #         while True:
            #             alt = random.choice(alternatives)
            #             self.username = alt.text
            #             try:
            #                 self.click(alt)
            #                 break
            #             except MoveTargetOutOfBoundsException:
            #                 pass
            #     else:
            #         self.user.username = generate_random_username(self.user.real_name)
            #         self.fill_input_text('#username', self.user.username)

        try:
            LOGGER.info('User %s signing up on twitter..' % self.user.username)
            self.go_to(settings.URLS['twitter_reg'])
            # esperamos a que se cargue bien el formulario
            self.wait_visibility_of_css_element('#full-name', timeout=15)

            # rellenamos
            self.fill_input_text('#full-name', self.user.real_name)

            self.fill_input_text('#email', self.user.email)
            check_email()

            self.fill_input_text('#password', self.user.password_twitter)

            self.fill_input_text('#username', self.user.username)
            check_username()

            self.click('input[name="submit_button"]')
            self.delay.seconds(10)

            # le damos al botón 'next' que sale en la bienvenida
            welcome_a = 'a[href="/welcome/recommendations"]'
            if self.check_visibility(welcome_a):
                self.click(welcome_a)

            self.wait_to_page_loaded()
            self.delay.seconds(7)

            wait_condition(lambda: 'congratulations' in self.browser.current_url, timeout=15)

            self.take_screenshot('twitter_registered_ok')

            # finalmente lo ponemos como registrado en twitter
            self.user.twitter_registered_ok = True
            self.user.save()
            LOGGER.info('User %s successfully signed up on twitter' % self.user.username)
        except Exception, e:
            self.take_screenshot('twitter_registered_fail')
            LOGGER.exception('User %s has errors signing up twitter account' % self.user.username)
            raise e

    def login(self):
        try:
            self.open_browser()
            self.go_to(settings.URLS['twitter_login'])
            if not self.user.is_kamikaze:
                self.click('.remember-forgot input')
            self.fill_input_text('#signin-email', self.user.username)
            self.fill_input_text('#signin-password', self.user.password_twitter)
            self.click('.front-signin button')
            self.wait_to_page_loaded()

            # si no es kamikaze comprobamos que no esté suspendida la cuenta
            if not self.user.is_kamikaze:
                if self.check_visibility('#account-suspended'):
                    conf_email_link = get_element(lambda: self.browser.find_element_by_partial_link_text('confirm your email'))
                    if conf_email_link:
                        # si la cuanta está suspendida por no haber comprobado el email
                        if not self.user.is_kamikaze:
                            self.click(conf_email_link)
                        self.user.mark_as_suspended()
                    else:
                        # intentamos levantar suspensión
                        cr = DeathByCaptchaResolver(self)

                        def submit_unsuspension():
                            cr.resolve_captcha(
                                self.get_css_element('#recaptcha_challenge_image'),
                                self.get_css_element('#recaptcha_response_field')
                            )
                            self.click('#suspended_help_submit')
                            self.delay.seconds(5)

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
                        self.delay.seconds(2)
                else:
                    user_not_found_el = get_element(lambda: self.get_css_element('#message-drawer'))
                    if user_not_found_el and 'The username and password you entered did not match our records' in user_not_found_el.text:
                        # si el usuario no se encuentra
                        self.user.mark_as_not_twitter_registered_ok()
                        raise
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
                from .hotmail import HotmailScrapper

                email_domain = self.user.get_email_account_domain()
                if email_domain == 'hotmail.com' or email_domain == 'outlook.com':
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
            if self.check_visibility('button.ProfileAvatarEditing-button'):
                self.download_pic_from_google()

                self.click('button.ProfileAvatarEditing-button')
                avatar_path = os.path.join(settings.PROJECT_ROOT, 'scrapper', 'avatars', '%s.png' % self.user.username)
                self.get_css_element('#photo-choose-existing input[type="file"]').send_keys(avatar_path)
                self.click('#profile_image_upload_dialog-dialog button.profile-image-save')
                # eliminamos el archivo que habíamos guardado para el avatar
                os.remove(avatar_path)

        def set_bio():
            self.fill_input_text('#user_description', self.get_quote())

        self.go_to(settings.URLS['twitter_login'])
        self.click('a.DashboardProfileCard-avatarLink')
        self.click('button.UserActions-editButton')
        self.delay.seconds(3)
        set_avatar()
        set_bio()
        self.click('.ProfilePage-editingButtons button.ProfilePage-saveButton')
        self.take_screenshot('profile_completed')
        self.user.twitter_profile_completed = True
        self.user.save()
        LOGGER.info('%s profile completed ok' % self.user.username)

    def create_bot(self):
        try:
            if settings.FAST_MODE:
                LOGGER.warning('Fast mode is enabled!')

            # abrimos ventana para scrapear twitter
            self.open_browser()

            # crea cuenta email
            if not self.user.is_kamikaze:
                self.check_proxy_works_ok()
                self.set_email_scrapper()
                if self.user.has_to_register_email():
                    self.signup_email_account()

            # crea cuenta twitter
            if self.user.has_to_register_twitter():
                self.sign_up()
            else:
                # si no se tiene que registrar en twitter lo logueamos para así poder
                # completar su perfil en caso de faltarle
                self.login()

            # confirma email de twitter y rellena perfil en twitter
            if not self.user.is_kamikaze:
                if self.user.has_to_confirm_tw_email():
                    self.email_scrapper.confirm_tw_email()

                self.email_scrapper.close_browser()

                if self.user.has_to_complete_tw_profile():
                    self.set_profile()

            self.user.it_works = True
            self.user.save()
        except Exception as ex:
            LOGGER.exception('Automated registrations failed for "%s"' % self.user.username)
            self.close()
            raise ex

    def close(self):
        if hasattr(self, 'email_scrapper'):
            self.email_scrapper.close_browser()
        self.close_browser()

    def send_tweet(self, msg):
        self.click('#global-new-tweet-button')
        # self.delay.seconds(1, force_delay=True)
        self.send_keys(msg)
        self.click('#global-tweet-dialog-dialog .tweet-button button')

        if self.check_visibility('#global-tweet-dialog'):
            # si aún aparece el diálogo de twitear es que no se envió ok
            LOGGER.info('Failure sending tweet from %s' % self.user.username)
            self.take_screenshot('failure_sending_tweet')

            # vemos si ha sido detectado como spammer
            if self.check_visibility('#spam_challenge_dialog-header'):
                raise BotDetectedAsSpammerException(self.user)

            self.send_special_key(Keys.ESCAPE)
        elif self.check_visibility('#spam_challenge_dialog-header'):
            raise BotDetectedAsSpammerException(self)
        else:
            LOGGER.info('Tweet sent ok from %s' % self.user.username)
            self.take_screenshot('tweet_sent_ok')

    def send_mention(self, username_to_mention, mention_msg):
        self.send_tweet('@' + username_to_mention + ' ' + mention_msg)
        LOGGER.info('Mention sent ok %s -> %s' % (self.user.username, username_to_mention))