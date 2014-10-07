# -*- coding: utf-8 -*-
from selenium.common.exceptions import MoveTargetOutOfBoundsException

from scrapper.scrapper import Scrapper, INVALID_EMAIL_DOMAIN_MSG
from scrapper.exceptions import TwitterEmailNotFound, BotDetectedAsSpammerException, BotMustVerifyPhone, \
    TwitterBotDontExistsOnTwitterException, FailureSendingTweetException, TwitterEmailNotConfirmed, \
    TwitterAccountSuspended
from scrapper.utils import *
from twitter_bots import settings


class TwitterScrapper(Scrapper):

    def sign_up(self):
        """Crea una cuenta de twitter con los datos dados. No guarda nada en BD, sólo entra en twitter y lo registra"""

        def check_email():
            while True:
                if self.check_visibility('.prompt.email .sidetip .checking.active'):
                    self.delay.seconds(0.5, force_delay=True)
                elif self.check_visibility('.prompt.email .sidetip .error.active'):
                    fucked_email = self.user.email
                    self.user.email_registered_ok = False
                    self.user.save()
                    raise Exception('Email %s exists on twitter' % fucked_email)

                elif self.check_visibility('.prompt.email .sidetip .ok.active'):
                    break

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
                            try:
                                self.click(alt)
                                self.user.username = alt.text
                                self.user.save()
                                break
                            except MoveTargetOutOfBoundsException:
                                pass
                    else:
                        self.user.username = generate_random_username(self.user.real_name)
                        self.fill_input_text('#username', self.user.username)
                # USERNAME OK
                elif self.check_visibility('.select-username .sidetip .ok.active'):
                    break

        try:
            settings.LOGGER.info('User %s signing up on twitter..' % self.user.username)
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

            # si pide teléfono
            if check_condition(lambda: 'phone_number' in self.browser.current_url, timeout=20):
                raise BotMustVerifyPhone(self.user)

            wait_condition(lambda: 'congratulations' in self.browser.current_url or
                                   'welcome' in self.browser.current_url)

            self.take_screenshot('twitter_registered_ok')

            # finalmente lo ponemos como registrado en twitter
            self.user.twitter_registered_ok = True
            self.user.save()
            settings.LOGGER.info('User %s successfully signed up on twitter' % self.user.username)
        except Exception, e:
            self.take_screenshot('twitter_registered_fail')
            settings.LOGGER.exception('Error on bot %s signing up twitter account' % self.user.username)
            raise e

    def is_logged_in(self):
        return self.check_visibility('#global-new-tweet-button')

    def clear_local_storage(self):
        # para que no aparezcan cositas de otras instancias de phantomjs
        self.browser.execute_script('localStorage.clear();')

    def login(self):
        """Hace todo el proceso de entrar en twitter y loguearse si fuera necesario por no tener las cookies guardadas"""
        try:
            self.go_to(settings.URLS['twitter_login'])

            # para ver si ya estamos logueados o no
            if not self.is_logged_in():
                self.fill_input_text('#signin-email', self.user.username)
                self.fill_input_text('#signin-password', self.user.password_twitter)
                self.click('.front-signin button')

            self.wait_to_page_loaded()
            self.check_account_exists()

            self.clear_local_storage()
            self.check_account_suspended()
        except Exception, e:
            settings.LOGGER.exception('Login on twitter error for %s' % self.user.username)
            raise e

    def check_account_suspended(self):
        """Una vez logueado miramos si fue suspendida la cuenta"""
        bot_is_suspended = lambda: self.get_css_element('#account-suspended') and \
                                   self.get_css_element('#account-suspended').is_displayed()
        if check_condition(bot_is_suspended):
            self.user.mark_as_suspended()

            if 'confirm your email' in self.get_css_element('#account-suspended').text:
                self.click('#account-suspended a')
                self.delay.seconds(4)
                raise TwitterEmailNotConfirmed(self.user)
            else:
                raise TwitterAccountSuspended(self.user)
        elif self.check_visibility('.resend-confirmation-email-link'):
            self.click('.resend-confirmation-email-link')
            self.user.twitter_confirmed_email_ok = False
            self.user.save()
            self.confirm_user_email()
            self.login()
        else:
            self.user.it_works = True
            self.user.save()

        # if self.check_visibility('#account-suspended'):
        #     conf_email_link = get_element(lambda: self.browser.find_element_by_partial_link_text('confirm your email'))
        #     if conf_email_link:
        #         # si la cuanta está suspendida por no haber comprobado el email
        #         self.click(conf_email_link)
        #         self.user.mark_as_suspended()
        #     else:
        #         # intentamos levantar suspensión
        #         cr = DeathByCaptchaResolver(self)
        #
        #         def submit_unsuspension():
        #             cr.resolve_captcha(
        #                 self.get_css_element('#recaptcha_challenge_image'),
        #                 self.get_css_element('#recaptcha_response_field')
        #             )
        #             self.click('#suspended_help_submit')
        #             self.delay.seconds(5)
        #
        #             if self.check_visibility('form.t1-form .error-occurred'):
        #                 cr.report_wrong_captcha()
        #                 submit_unsuspension()
        #
        #         self.user.mark_as_suspended()
        #         self.click(self.get_css_element('#account-suspended a'))
        #         self.click('#checkbox_discontinue')
        #         self.click('#checkbox_permanent')
        #         submit_unsuspension()
        # elif self.check_visibility('button.resend-confirmation-email-link'):
        #         self.click('button.resend-confirmation-email-link')
        #         self.delay.seconds(2)
        #         self.user.twitter_confirmed_email_ok = False
        #         self.user.save()

    def check_account_exists(self):
        "Mira si tras intentar loguearse el usuario existe o no en twitter"
        if 'error' in self.browser.current_url:
            raise TwitterBotDontExistsOnTwitterException(self.user)

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
            settings.LOGGER.info('Confirming email %s for twitter user: %s..' % (self.user.email, self.user.username))
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
                settings.LOGGER.info('Twitter email confirmed ok for %s with email: %s' % (self.user.username, self.user.email))
        except TwitterEmailNotFound:
            self.login()
            self.confirm_user_email()
        except Exception, e:
            settings.LOGGER.exception('Error confirming twitter email. User: %s, email: %s' %(self.user.username, self.user.email))
            raise e

    def set_profile(self):
        """precondición: estar logueado y en la home"""
        def set_avatar():
            avatar_path = os.path.join(settings.AVATARS_DIR, '%s.png' % self.user.username)
            try:
                if self.check_visibility('button.ProfileAvatarEditing-button'):
                    self.download_pic_from_google()

                    self.click('button.ProfileAvatarEditing-button')
                    self.get_css_element('#photo-choose-existing input[type="file"]').send_keys(avatar_path)
                    self.click('#profile_image_upload_dialog-dialog button.profile-image-save')
                    # eliminamos el archivo que habíamos guardado para el avatar
                    os.remove(avatar_path)
                    self.user.twitter_avatar_completed = True
                    self.user.save()
            except Exception:
                settings.LOGGER.exception('Error setting avatar for bot %s' % self.user.username)

        def set_bio():
            try:
                self.fill_input_text('#user_description', self.get_quote())
                self.user.twitter_bio_completed = True
                self.user.save()
            except Exception:
                settings.LOGGER.exception('Error setting bio for bot %s' % self.user.username)

        self.login()
        self.click('ul#global-actions li.profile a')  # página de perfil
        self.click('button.UserActions-editButton')  # botón de editar
        self.delay.seconds(3)
        if not self.user.twitter_avatar_completed and settings.TW_SET_AVATAR:
            set_avatar()
        if not self.user.twitter_bio_completed and settings.TW_SET_BIO:
            set_bio()
        self.click('.ProfilePage-editingButtons button.ProfilePage-saveButton')
        self.delay.seconds(7)
        self.take_screenshot('profile_completed')
        if self.user.has_tw_profile_completed():
            settings.LOGGER.info('Profile completed ok for bot %s' % self.user.username)
        else:
            settings.LOGGER.info('Profile completed with errors for bot %s' % self.user.username)

    def scrape_bot_creation(self):
        try:
            t1 = datetime.datetime.utcnow()
            if settings.FAST_MODE and not settings.TEST_MODE:
                settings.LOGGER.warning('Fast mode only avaiable on test mode!')
                settings.FAST_MODE = False

            # abrimos ventana para scrapear twitter
            self.screenshots_dir = 'twitter'
            self.open_browser()

            # crea cuenta email
            self.set_email_scrapper()
            if self.user.has_to_register_email():
                self.check_proxy_works_ok()
                self.signup_email_account()

            # crea cuenta twitter
            if self.user.has_to_register_twitter():
                self.sign_up()

            # confirma email de twitter y rellena perfil en twitter
            if self.user.has_to_confirm_tw_email():
                self.email_scrapper.confirm_tw_email()

            self.email_scrapper.close_browser()

            if self.user.has_to_complete_tw_profile():
                self.login()
                self.set_profile()

            self.user.it_works = True
            self.user.save()
            t2 = datetime.datetime.utcnow()
            diff_secs = (t2 - t1).seconds
            settings.LOGGER.info('Bot "%s" creation scrapped sucessfully in %s seconds' % (self.user.username, diff_secs))
        except Exception as ex:
            settings.LOGGER.exception('Error scraping bot "%s" for creation' % self.user.username)
            self.close()
            raise ex

    def close(self):
        if hasattr(self, 'email_scrapper'):
            self.email_scrapper.close_browser()
        self.close_browser()

    def send_tweet(self, tweet):
        self.click('#global-new-tweet-button')
        self.send_keys(tweet.compose())

        # self.click('#tweet-box-mini-home-profile')
        # self.delay.seconds(1, force_delay=True)
        # self.fill_input_text('#tweet-box-mini-home-profile', msg)

        self.click('#global-tweet-dialog-dialog .tweet-button button')
        self.delay.seconds(5)

        if self.check_visibility('#global-tweet-dialog'):
            # si aún aparece el diálogo de twitear es que no se envió ok
            # si el  se elimina y se marca el bot como inválido
            settings.LOGGER.info('Failure sending tweet from %s' % self.user.username)
            self.take_screenshot('failure_sending_tweet')
            tweet.delete()
            raise FailureSendingTweetException()
        else:
            settings.LOGGER.info('Tweet sent ok from %s' % self.user.username)
            self.take_screenshot('tweet_sent_ok')

        self.delay.seconds(7)

    def send_mention(self, username_to_mention, mention_msg):
        self.send_tweet('@' + username_to_mention + ' ' + mention_msg)
        settings.LOGGER.info('Mention sent ok %s -> %s' % (self.user.username, username_to_mention))