# -*- coding: utf-8 -*-
from selenium.webdriver.common.keys import Keys
from core.managers import mutex
from core.scrapper.scrapper import Scrapper
from core.scrapper.captcha_resolvers import DeathByCaptchaResolver
from core.scrapper.exceptions import BotMustVerifyPhone, TwitterBotDontExistsOnTwitterException, \
    FailureSendingTweetException, TwitterEmailNotConfirmed, TwitterAccountDead, ProfileStillNotCompleted, \
    PageNotReadyState, TwitterAccountSuspendedAfterTryingUnsuspend, ConnectionError, TweetAlreadySent
from core.scrapper.utils import *
from selenium.common.exceptions import MoveTargetOutOfBoundsException
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
                    # self.user.email_registered_ok = False
                    # self.user.save()
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
            self.logger.info('Signing up on twitter..')
            self.go_to(settings.URLS['twitter_reg'])
            self.wait_to_page_readystate()

            # hay dos maneras de rellenar el formulario de registro en twitter, según como nos aparezca la interfaz
            if self.check_visibility('#next_button'):
                self.fill_input_text('#email', self.user.email)
                check_email()
                self.click('#next_button')
                self.fill_input_text('#full-name', self.user.real_name)
                self.click('#submit_button')
                self.fill_input_text('#password', self.user.password_twitter)
                self.click('#submit_button')
                self.fill_input_text('#username', self.user.username)
                check_username()
                self.click('#submit_button')
            elif self.check_visibility('#full-name'):
                self.fill_input_text('#full-name', self.user.real_name)
                self.fill_input_text('#email', self.user.email)
                check_email()
                self.fill_input_text('#password', self.user.password_twitter)
                self.fill_input_text('#username', self.user.username)
                check_username()
                self.try_to_click('input[name="submit_button"]', 'input#submit_button')

            self.delay.seconds(10)

            # le damos al botón 'next' que sale en la bienvenida (si lo hay)
            self.try_to_click('a[href="/welcome/recommendations"]' )

            self.wait_to_page_readystate()
            self.delay.seconds(7)

            # si pide teléfono
            if check_condition(lambda: 'phone_number' in self.browser.current_url, timeout=20):
                raise BotMustVerifyPhone(self)

            wait_condition(lambda: 'congratulations' in self.browser.current_url or
                                   'welcome' in self.browser.current_url or
                                   'start' in self.browser.current_url)

            self.take_screenshot('twitter_registered_ok', force_take=True)

            # finalmente lo ponemos como registrado en twitter
            self.user.twitter_registered_ok = True
            self.user.save()
            self.logger.info('Twitter account registered successfully')
        except Exception, e:
            self.take_screenshot('twitter_registered_fail', force_take=True)
            self.logger.exception('Error registering twitter account')
            raise e

    def is_logged_in(self):
        return self.check_visibility('#global-new-tweet-button')

    def login(self):
        """Hace todo el proceso de entrar en twitter y loguearse si fuera necesario por no tener las cookies guardadas"""
        try:
            self.go_to(settings.URLS['twitter_login'])
            self.wait_to_page_readystate()

            # para ver si ya estamos logueados o no
            if not self.is_logged_in():
                self.fill_input_text('#signin-email', self.user.username)
                self.fill_input_text('#signin-password', self.user.password_twitter)
                self.click('.front-signin button')

            self.wait_to_page_readystate()
            self.check_account_exists()

            self.clear_local_storage()
            self.check_account_suspended()
        except (ConnectionError,
                PageNotReadyState) as e:
            raise e
        except Exception as e:
            self.logger.error('Login on twitter error')
            self.take_screenshot('login_failure', force_take=True)
            raise e

    def lift_suspension(self):
        # intentamos levantar suspensión
        def submit_unsuspension(attempt):
            if attempt == 5:
                if settings.MARK_BOT_AS_DEATH_AFTER_TRYING_LIFTING_SUSPENSION:
                    raise TwitterAccountDead(self)
                else:
                    raise TwitterAccountSuspendedAfterTryingUnsuspend(self)
            else:
                self.logger.info('Lifting twitter account suspension (attempt %i)..' % attempt)

                cr.resolve_captcha(
                    self.get_css_element('#recaptcha_challenge_image'),
                    self.get_css_element('#recaptcha_response_field')
                )

                self.try_to_click('#checkbox_discontinue')
                self.try_to_click('#checkbox_permanent')

                self.click('#suspended_help_submit')
                self.delay.seconds(5)

                if self.check_visibility('form.t1-form .error-occurred'):
                    cr.report_wrong_captcha()
                    submit_unsuspension(attempt+1)
                else:
                    # si la suspensión se levantó bien..
                    self.user.unmark_as_suspended()

        self.user.mark_as_suspended()
        self.click(self.get_css_element('#account-suspended a'))
        self.wait_to_page_readystate()
        cr = DeathByCaptchaResolver(self)
        submit_unsuspension(attempt=0)

    def check_account_suspended(self):
        """Una vez logueado miramos si fue suspendida la cuenta"""
        bot_is_suspended = lambda: self.get_css_element('#account-suspended') and \
                                   self.get_css_element('#account-suspended').is_displayed()
        if check_condition(bot_is_suspended):
            if 'confirm your email' in self.get_css_element('#account-suspended').text:
                self.click('#account-suspended a')
                self.delay.seconds(4)
                raise TwitterEmailNotConfirmed(self)
            else:
                self.lift_suspension()
        elif self.check_visibility('.resend-confirmation-email-link'):
            self.click('.resend-confirmation-email-link')
            self.delay.seconds(4)
            raise TwitterEmailNotConfirmed(self)
        else:
            self.user.is_suspended = False
            self.user.save()

    def check_account_exists(self):
        "Mira si tras intentar loguearse el usuario existe o no en twitter"
        if 'error' in self.browser.current_url:
            raise TwitterBotDontExistsOnTwitterException(self)

    def twitter_page_is_loaded_on_new_window(self):
        """mira si se cargó por completo la página en la ventana nueva que se abre al pinchar en el enlace
        del email de confirmación enviado por twitter"""
        is_twitter_confirm_window_opened = len(self.browser.window_handles) == self.num_prev_opened_windows + 1
        if is_twitter_confirm_window_opened:
            self.switch_to_window(-1)
            return self.browser.execute_script("return document.readyState;") == 'complete'
        else:
            return False

    def set_profile(self):
        """precondición: estar logueado y en la home"""
        def set_avatar():
            self.logger.info('Setting twitter avatar..')
            avatar_path = os.path.join(settings.AVATARS_DIR, '%s.png' % self.user.username)
            try:
                self.download_pic_from_google()

                try:
                    self.click('.ProfileAvatar a')
                    if not self.check_visibility('#photo-choose-existing'):
                        self.click('button.ProfileAvatarEditing-button')
                except:
                    self.click('button.ProfileAvatarEditing-button')

                self.get_css_element('#photo-choose-existing input[type="file"]').send_keys(avatar_path)
                self.click('#profile_image_upload_dialog-dialog button.profile-image-save')
                # eliminamos el archivo que habíamos guardado para el avatar
                os.remove(avatar_path)
                return True
            except Exception:
                self.logger.exception('Error setting twitter avatar')
                self.take_screenshot('set_avatar_failure', force_take=True)
                return False

        def set_bio():
            try:
                self.logger.info('Setting twitter bio..')
                self.fill_input_text('#user_description', self.get_quote())
                return True
            except Exception:
                self.logger.exception('Error setting twitter bio')
                self.take_screenshot('set_bio_failure', force_take=True)
                return False

        try:
            self.login()

            # vamos a página de perfil haciendo click en cualquier botón que nos lleve ahí
            self.click('.DashboardProfileCard-name a')  # vamos a su página de perfil
            self.click('button.UserActions-editButton')  # damos a botón de editar
            self.delay.seconds(3)

            avatar_completed = False
            bio_completed = False
            if self.user.has_to_set_tw_avatar():
                avatar_completed = set_avatar()
            if self.user.has_to_set_tw_bio():
                bio_completed = set_bio()
            self.click('.ProfilePage-editingButtons button.ProfilePage-saveButton')  # click en guardar perfil
            self.delay.seconds(7)

            # sólo una vez se hizo click en el botón de guardar reflejamos cambios en BD
            if avatar_completed:
                self.user.twitter_avatar_completed = True
                self.user.save()
            if bio_completed:
                self.user.twitter_bio_completed = True
                self.user.save()

            if self.user.has_tw_profile_completed():
                self.logger.info('Profile completed sucessfully')
                self.take_screenshot('profile_completed_ok', force_take=True)
            else:
                raise ProfileStillNotCompleted(self)
        except Exception as ex:
            self.logger.exception('Error creating twitter profile')
            self.take_screenshot('profile_creation_failure', force_take=True)
            raise ex

    def close(self):
        if hasattr(self, 'email_scrapper'):
            self.email_scrapper.close_browser()
        self.close_browser()

    def send_tweet(self, tweet):
        def is_plain_tweet():
            return type(tweet) is str or type(tweet) is unicode

        def print_tweet_id():
            return tweet if is_plain_tweet() else str(tweet.pk)

        def print_tweet_type():
            return 'PLAIN' if is_plain_tweet() else tweet.print_type()

        def print_tweet_msg():
            return tweet if is_plain_tweet() else tweet.compose()

        def check_sent_ok():
            # si aún aparece el diálogo de twitear es que no se envió ok
            if self.check_visibility('#global-tweet-dialog'):

                # miramos si sale mensajito de 'you already sent this tweet'
                if self.check_visibility('#message-drawer .message-text'):
                    raise TweetAlreadySent(self, tweet, 'Tweet %s was already sent by bot %s' %
                                           (print_tweet_id(), self.user.username))
                else:
                    raise FailureSendingTweetException(self,
                        'Error on bot %s sending tweet %s' % (self.user.username, print_tweet_id()))
            else:

                try:
                    mutex.acquire()
                    tweet.sent_ok = True
                    tweet.date_sent = utc_now()
                    tweet.save()
                finally:
                    mutex.release()

                settings.LOGGER.info('Bot %s sent ok tweet %s [%s]' % (self.user.username, print_tweet_id(), print_tweet_type()))
                self.take_screenshot('tweet_sent_ok', force_take=True)

        self.click('#global-new-tweet-button')

        if is_plain_tweet():
            self.send_keys(tweet)
        else:
            self.send_keys(tweet.compose())

            if tweet.has_image():
                el = self.browser.find_element_by_xpath("//*[@id=\"global-tweet-dialog-dialog\"]"
                                                        "/div[2]/div[4]/form/div[2]/div[1]/div[1]/div/label/input")
                el.send_keys(tweet.get_image().img.path)

        self.click('#global-tweet-dialog-dialog .tweet-button button')
        self.delay.seconds(5)
        check_sent_ok()
        self.delay.seconds(7)

    def send_mention(self, username_to_mention, mention_msg):
        self.send_tweet('@' + username_to_mention + ' ' + mention_msg)
        self.logger.info('Mention sent ok %s -> %s' % (self.user.username, username_to_mention))

