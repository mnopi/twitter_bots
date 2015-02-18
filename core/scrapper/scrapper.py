# -*- coding: utf-8 -*-

import sys
import urllib
import numpy
import psutil
from selenium.common.exceptions import NoSuchFrameException, TimeoutException, NoSuchElementException
from selenium.webdriver import ActionChains, DesiredCapabilities, Proxy
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium import webdriver
from core.managers import mutex
from .delay import Delay
from .exceptions import RequestAttemptsExceededException, ProxyConnectionError, ProxyTimeoutError, \
    InternetConnectionError, ProxyUrlRequestError, IncompatibleUserAgent, PageNotReadyState, NoElementToClick, \
    BlankPageError, ProxyAccessDeniedError
import my_phantomjs_webdriver
from project.models import ProxiesGroup
from utils import *
from twitter_bots import settings

INVALID_EMAIL_DOMAIN_MSG = 'Invalid email domain used, only accepts: hushmail.com, gmail.com, hotmail.com'


class Scrapper(object):
    # cada scrapper (hotmail, twitter..) tendrá su propia carpeta para capturar los pantallazos
    CMD_KEY = Keys.COMMAND if sys.platform == 'darwin' else Keys.CONTROL

    def __init__(self, user=None, force_firefox=False, screenshots_dir=None):
        self.user = user
        self.delay = Delay(user)
        self.force_firefox = force_firefox or settings.FORCE_FIREFOX
        # contiene el header USER-AGENT a enviar en las peticiones HTTP, esto muestra el S.O. usado,
        # navegador, etc para el servidor que recibe la petición (twitter, gmail, etc)
        self.browser = None  # navegador a usar por el webdriver de selenium
        self.captcha_el = None  # parte del DOM donde aparece la imágen del captcha
        self.captcha_sol = None  # parte del DOM donde se introducirá solución al captcha
        self.captcha_res = None  # solución al captcha ofrecida por deathbycaptcha
        self.form_errors = {}  # errores que ocurran en algún formulario
        self.screenshots_dir = screenshots_dir or ''
        self.screenshot_num = 1  # contador para capturas de pantalla
        self.current_mouse_position = {'x': 0, 'y': 0}
        self.logger = ScrapperLogger(self)

    def check_proxy_works_ok(self):
        """Mira si funciona correctamente el proxy que se supone que tenemos contratado"""
        self.go_to('http://twitter.com')

    def set_screenshots_dir(self, dir_name):
        self.screenshots_dir = dir_name
        self.screenshot_num = 1

    def open_browser(self, renew_user_agent=False):
        """Devuelve el navegador a usar"""

        def get_firefox():
            # PARA USAR PROXY CON AUTENTICACIÓN BASIC HTTP EN FIREFOX:
            #   1. se crea el perfil dado con el comando:
            #       /Applications/Firefox.app/Contents/MacOS/firefox-bin -p
            #   2. donde la config de proxy marcar la casilla de abajo "recordar contraseña guardada..
            #   3. la ruta hacia la carpeta de ese perfil la metemos aquí
            #profile = webdriver.FirefoxProfile('/Users/rmaja/Library/Application Support/Firefox/Profiles/gdq2kd20.perf')
            profile = webdriver.FirefoxProfile()

            if settings.USE_PROXY and self.user.proxy_for_usage:
                profile.set_preference('network.proxy.type', 1)
                profile.set_preference("network.proxy.http", proxy_ip)
                profile.set_preference("network.proxy.http_port", proxy_port)
                profile.set_preference("network.proxy.ssl", proxy_ip)
                profile.set_preference("network.proxy.ssl_port", proxy_port)
                profile.set_preference('network.proxy.socks', proxy_ip)
                profile.set_preference('network.proxy.socks_port', proxy_port)

            # le metemos un user-agent random para camuflar el webdriver de cara a twitter etc
            profile.set_preference('general.useragent.override', self.user.user_agent)
            # lenguaje inglés siempre
            profile.set_preference('intl.accept_languages', 'en-us')
            #profile.set_preference('network.automatic-ntlm-auth.trusted-uris', 'google.com')
            self.browser = webdriver.Firefox(profile)

        def get_chrome():
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--proxy-server=%s:%s' % (proxy_ip, str(proxy_port)))
            self.browser = webdriver.Chrome(chrome_options=chrome_options)

        def get_panthom():
            service_args = []

            # proxy
            if settings.USE_PROXY and self.user.proxy_for_usage:
                service_args = [
                    '--proxy=%s:%i' % (proxy_ip, proxy_port),
                    '--cookies-file=%s' % os.path.join(settings.PHANTOMJS_COOKIES_DIR, '%i_%s.txt' %
                                                       (self.user.id, '_'.join(self.user.real_name.split(' ')))),
                    '--ssl-protocol=any',
                    # '--local-storage-path=%s' % settings.PHANTOMJS_LOCALSTORAGES_PATH,
                    # '--local-storage-quota=1024',
                ]

            # user-agent
            dcap = dict(DesiredCapabilities.PHANTOMJS)
            dcap["phantomjs.page.settings.userAgent"] = (self.user.user_agent)
            dcap["phantomjs.page.customHeaders.Accept-Language"] = 'en-us'

            self.browser = my_phantomjs_webdriver.MyWebDriver(
                settings.PHANTOMJS_BIN_PATH,
                service_args=service_args,
                desired_capabilities=dcap,
                service_log_path=os.path.join(settings.LOGS_DIR, 'ghostdriver.log')
            )

        # si ya hay navegador antes de abrirlo nos aseguramos que esté cerrado para no acumular una instancia más
        # cada vez que abrimos
        if self.browser:
            try:
                self.close_browser()
            except Exception:
                pass

        #
        # seteamos el correspondiente proxy en el caso de usar proxy
        if settings.USE_PROXY:
            self.user.check_proxy_ok()

            proxy_ip = self.user.proxy_for_usage.proxy.split(':')[0]
            proxy_port = int(self.user.proxy_for_usage.proxy.split(':')[1])

        if not self.user.user_agent:
            self.change_user_agent()

        #
        # elegimos tipo de navegador
        user_webdriver = self.user.get_webdriver()
        if self.force_firefox or user_webdriver == ProxiesGroup.FIREFOX:
            get_firefox()
        elif user_webdriver == ProxiesGroup.CHROME:
            get_chrome()
        elif user_webdriver == ProxiesGroup.PHANTOMJS:
            get_panthom()

        self.browser.maximize_window()
        self.browser.set_page_load_timeout(settings.PAGE_LOAD_TIMEOUT)
        self.logger.debug('%s instance opened successfully' % self.user.get_webdriver())

    def close_browser(self):
        try:
            pid = self.browser.service.process.pid
            try:
                self.logger.debug('%s instance closing..' % self.user.get_webdriver())
                self.browser.quit()
                self.logger.debug('..%s instance closed ok' % self.user.get_webdriver())
            finally:
                # comprobamos que no quede el proceso abierto
                for proc in psutil.process_iter():
                    if proc.pid == pid:
                        self.logger.debug('..%s instance stills opened, killing process PID=%d..' %
                                          (self.user.get_webdriver(), pid))
                        try:
                            proc.kill()
                            self.logger.debug('..process PID=%d killed ok' % pid)
                        except Exception as e:
                            self.logger.error('..process PID=%d not killed ok!' % pid)
                            raise e
                        finally:
                            break
        except Exception as ex:
            if not self.browser:
                self.logger.warning('%s instance was not opened browser' % self.user.get_webdriver())
            else:
                self.logger.error('Error closing %s browser instance' % self.user.get_webdriver())
                raise ex

    def open_url_in_new_tab(self, url):
        self.browser.find_element_by_tag_name("body").send_keys(self.CMD_KEY + 't')
        self.delay.seconds(seconds=4)
        self.browser.get(url)

    def open_url_in_new_window(self, url):
        """
        NO FUNCIONA CON PHANTOMJS!
        """
        if self.user.webdriver == 'PH':
            self.browser.execute_script("window.open('" + url + "');")
        else:
            ActionChains(self.browser).key_down(self.CMD_KEY).send_keys('n').key_up(self.CMD_KEY).perform()
        self.switch_to_window(-1)
        self.go_to(url)

    def switch_to_window(self, i):
        "Cambia a la ventana de ínidice i. Para ir a la última abierta: switch_to_window(-1)"
        self.browser.switch_to.window(self.browser.window_handles[i])

    def clean_form_errors(self):
        """Limpia el scrapper de errores, captcha, etc"""
        self.form_errors = {}

    def wait_visibility_of_css_element(self, css_element, timeout=5):
        WebDriverWait(self.browser, timeout).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, css_element)
            )
        )

    def wait_invisibility_of_css_element(self, css_element, timeout=5):
        WebDriverWait(self.browser, timeout).until(
            EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, css_element)
            )
        )

    def get_css_element(self, css_selector, timeout=7):
        try:
            return WebDriverWait(self.browser, timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, css_selector)
                )
            )
        except Exception:
            return None

    def get_css_elements(self, css_selector, timeout=7):
        try:
            return WebDriverWait(self.browser, timeout).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, css_selector)
                )
            )
        except Exception:
            return None

    def check_visibility(self, el, **kwargs):
        """
        Se comprueba que el elemento 'el' existe, dándole una espera máxima de 'timeout' segundos
        """
        def is_visible_css():
            "Mira a partir de un css selector (string)"
            if 'timeout' in kwargs and kwargs['timeout']:
                try:
                    self.wait_visibility_of_css_element(el, **kwargs)
                    return True
                except Exception:
                    return False
            else:
                return not self.check_invisibility(el, **kwargs)

        def is_visible_obj():
            "Mira a partir del obj 'el' pasado por parámetro"
            if 'timeout' in kwargs and kwargs['timeout']:
                try:
                    if el:
                        wait_condition(lambda: el.is_displayed(), **kwargs)
                        return True
                    else:
                        return False
                except Exception:
                    return False
            else:
                return not self.check_invisibility(el, **kwargs)

        if type(el) is str:
            return is_visible_css()
        else:
            return is_visible_obj()

    def check_invisibility(self, el, **kwargs):
        def is_invisible_css():
            try:
                self.wait_invisibility_of_css_element(el, **kwargs)
                return True
            except Exception:
                return False

        def is_invisible_obj():
            try:
                if not el:
                    return True
                else:
                    wait_condition(lambda: not el.is_displayed(), **kwargs)
                    return False
            except Exception:
                return True

        if type(el) is str:
            return is_invisible_css()
        else:
            return is_invisible_obj()


    def login_email_account(self):
        from .accounts.hotmail import HotmailScrapper

        email_domain = self.user.get_email_account_domain()
        if email_domain == 'hotmail.com':
            self.email_scrapper = HotmailScrapper(self.user)
        else:
            raise Exception(INVALID_EMAIL_DOMAIN_MSG)

        self.email_scrapper.login()

    def get_usa_zip_code(self, state=None, city=None):
        """
        {
            'California': {
                state_short: 'CA',
                zip_codes: {
                    Sacramento: [94203, 94209],
                    ...
                }
            },
            ...
        }
        """
        # self.open_url_in_new_window('http://www.phaster.com/zip_code.html')
        # self.switch_to_window(-1)
        # states = {}
        # rows = self.browser.find_elements_by_css_selector('table')[0].find_elements_by_css_selector('tr')[1:]
        # for row in rows:
        #     cols = row.find_elements_by_css_selector('td')
        #     g = re.search("(?P<state>.*) .*\((?P<state_short>.*)\)", cols[0].text)
        #
        #     state_dict = {}
        #     state_dict['state_short'] = g.group('state_short')
        #     cities = [c for c in cols[1].text.split('\n') if c != ' ']
        #     zip_codes = [z for z in cols[2].text.split('\n') if z != ' ']
        #     state_dict['zip_codes'] = {}
        #     for i in range(len(cities)):
        #         state_dict['zip_codes'][cities[i]] = re.findall(r'\d+', zip_codes[i])
        #
        #     state = g.group('state')
        #     states[state] = state_dict

        def get_random():
            state = states[random.choice(states.keys())]
            zip_code = state['zip_codes'][random.choice(state['zip_codes'].keys())]
            if len(zip_code) == 2:
                zip_code = str(random.randint(int(zip_code[0]), int(zip_code[1])))
                if len(zip_code) == 4:
                    zip_code = '0' + zip_code
            else:
                zip_code = str(zip_code[0])
            return zip_code

        json_data = open(os.path.join(os.path.dirname(__file__), 'zip_codes.json'))
        states = simplejson.load(json_data)
        json_data.close()

        if not state and not city:
            return get_random()

    def wait_to_page_readystate(self):
        try:
            self.logger.debug('waiting to page readystate..: %s' % self.browser.current_url)
            wait_condition(
                lambda: self.browser.execute_script("return document.readyState;") == 'complete',
                timeout=settings.PAGE_READYSTATE_TIMEOUT
            )
            self.logger.debug('..ready')
            self.take_screenshot('page_readystate')
        except:
            raise PageNotReadyState(self)

    def switch_to_frame(self, frame, timeout=20):
        wait_start = utc_now()
        try:
            self.browser.switch_to.frame(frame)
        except NoSuchFrameException:
            time.sleep(0.5)
            diff = utc_now() - wait_start
            if diff.seconds >= timeout:
                raise Exception('Waiting iframe %s timeout' % frame)
            self.switch_to_frame(frame, timeout)

    def go_to(self, url, timeout=None, wait_page_loaded=False):

        def proxy_works():
            """Para ver que el proxy funciona comprobamos contra google"""
            scr = Scrapper(self.user)
            scr.open_browser()
            try:
                scr.browser.get('http://google.com')
                return 'google' in scr.browser.title.lower()
            except TimeoutException:
                return False

        def internet_connection_works():
            """Para ver que la conexión a internet funciona lanzamos el phantom sin ir a través de proxy"""
            browser = webdriver.PhantomJS(settings.PHANTOMJS_BIN_PATH)
            try:
                browser.get('http://google.com')
                return 'google' in browser.title.lower()
            except TimeoutException:
                return False

        try:
            if timeout:
                self.browser.set_page_load_timeout(timeout)
            self.browser.get(url)
            if self.browser.page_source == '<html><head></head><body></body></html>':
                raise BlankPageError(self, url)
            elif 'access denied' in self.browser.title.lower():
                raise ProxyAccessDeniedError(self, url)
            else:
                self.check_user_agent_compatibility()
                self._quit_focus_from_address_bar()
                self.logger.debug('go_to: %s' % url)
                self.take_screenshot('go_to')
        except (TimeoutException, BlankPageError, ProxyAccessDeniedError) as e:
            if type(e) is TimeoutException:
                self.logger.warning('Timeout loading url %s' % url)

            if proxy_works():
                # si el proxy funciona es que el fallo es específico de pedir esa url en concreto
                raise ProxyUrlRequestError(self, url)
            elif internet_connection_works():
                # si el proxy no funciona y sí la conexión a internet
                raise ProxyConnectionError(self.user)
            else:
                raise InternetConnectionError()
        except Exception, e:
            settings.LOGGER.exception('error')
            raise e
        finally:
            if timeout:
                # si hubo timeout entonces restauramos al puesto en settings
                self.browser.set_page_load_timeout(settings.PAGE_LOAD_TIMEOUT)

    def check_user_agent_compatibility(self):
        """Dice si el user agent usado es de móvil o no compatible"""
        if check_condition(lambda : 'mobile' in self.browser.current_url):
            self.change_user_agent()
            self.open_browser()

    def change_user_agent(self):
        self.user.user_agent = generate_random_desktop_user_agent()
        self.user.save()
        self.logger.info('User agent has changed to %s' % self.user.user_agent)

    def wait_until_closed_windows(self):
        while self.browser.window_handles:
            time.sleep(0.5)

    def fill_input_text(self, el, txt, attempt=0):
        """mousemoving"""
        self.click(el)
        self._clear_input_text(el)
        self.send_keys(txt)
        self.delay.box_switch()

    def _clear_input_text(self, el):
        if type(el) is str:
            el = self.get_css_element(el)

        typed_before_txt = el.get_attribute('value')
        if typed_before_txt:
            ActionChains(self.browser).key_down(Keys.ALT).perform()
            self.send_special_key(Keys.ARROW_RIGHT)
            ActionChains(self.browser).key_up(Keys.ALT).perform()
            self.delay.key_stroke()

            for c in typed_before_txt:
                self.send_special_key(Keys.BACKSPACE)

    def click(self, el):
        # def get_offsets():
        #     """Cuando se hace move_to_element sobre el elemento 'el' el cursor se coloca en el centro de
        #     dicho elemento. Vamos a introducir un offset aleatorio para que no dé siempre en el mismo centro"""
        #     half_width = ((el.size['width'] / 2) - 1)
        #     bounds = half_width / 2  # el límite donde se hace click es en la mitad del límite supuestamente clickable
        #     offset_x_neg = random.randint(1, bounds) * -1
        #     offset_x_pos = random.randint(1, bounds)
        #     offset_x = random.choice([offset_x_neg, offset_x_pos])
        #
        #     half_height = ((el.size['height'] / 2) - 1)
        #     bounds = half_height / 2
        #     offset_y_neg = random.randint(1, bounds) * -1
        #     offset_y_pos = random.randint(1, bounds)
        #     offset_y = random.choice([offset_y_neg, offset_y_pos])
        #
        #     return offset_x, offset_y

        # todo: meter una trayectoria aleatoria
        self.delay.during_mousemove()

        el_str = None
        if type(el) is str:
            el_str = el
            el = self.get_css_element(el)

        # si el elemento sobre el que se hace click no es un string css sino un objeto..
        if not el_str:
            try:
                el_str = el.text or 'without_text_el'
            except:
                try:
                    el_str = el.tag_name
                except:
                    el_str = 'unnamed_el'

        try:
            if settings.RANDOM_OFFSETS_ON_EL_CLICK:
                x_bound = el.size['width'] - 1  # el límite hasta donde se puede offsetear el click es el ancho
                y_bound = el.size['height'] - 1

                x_offset = random.randint(1, x_bound)
                y_offset = random.randint(1, y_bound)
                ActionChains(self.browser).move_to_element_with_offset(el, x_offset, y_offset).click().perform()
            else:
                ActionChains(self.browser).move_to_element(el).click().perform()
        except AttributeError:
            raise NoElementToClick(self, el_str)

        self.delay.box_switch()

        msg = 'click >> %s' % el_str
        self.take_screenshot(msg)
        self.logger.debug(msg)

    def try_to_click(self, *css_elements, **kwargs):
        for el in css_elements:
            if self.check_visibility(el, **kwargs):
                self.click(el)
                break

    def _quit_focus_from_address_bar(self):
        self.send_special_key(Keys.TAB)
        self.delay.key_stroke()
        self.send_special_key(Keys.TAB)
        self.delay.key_stroke()

    def send_special_key(self, special_key):
        "Para intro, tab.."
        ActionChains(self.browser).send_keys(special_key).perform()
        self.delay.key_stroke()

    def send_keys(self, keys):
        """Escribe cada caracter entre 0.2 y 0.9 segs de forma aleatoria, dando la impresión de
        que escriba un humano. se termina con un retardo mayor para que dé la impresión de que es un humano
        el que cambia de casilla en el formulario"""
        if type(keys) is int:
            keys = str(keys)

        for key in keys:
            ActionChains(self.browser).send_keys(key).perform()
            self.delay.key_stroke()

        self.logger.debug('send_keys >> "%s"' % keys)
        self.take_screenshot('send_keys')

    def download_pic_from_google(self):
        """Pilla de google una imágen y la guarda en disco"""
        def get_img():
            "Devuelve la imágen de la lista de resultados sobre la que luego haremos click para descargarla"
            g_scrapper.fill_input_text(
                'input[name="q"]',
                names.get_full_name(gender=self.user.get_gender_display())
            )
            g_scrapper.send_special_key(Keys.ENTER)
            g_scrapper.wait_to_page_readystate()
            g_scrapper.delay.seconds(3)

            if g_scrapper.check_visibility('#rg_s .rg_di'):
                imgs = g_scrapper.get_css_elements('#rg_s .rg_di')
                if imgs:
                    num_attempts = 0
                    while num_attempts < SEARCH_ATTEMPTS:
                        img = random.choice(imgs).find_element_by_css_selector('img')
                        if img.size['width'] >= MIN_RES and img.size['height'] >= MIN_RES:
                            return img
                        else:
                            num_attempts += 1
                    get_img()
                else:
                    # si no se encontró ninguna imagen con el suficiente tamaño se vuelve a buscar con otro nombre
                    get_img()
            else:
                g_scrapper.logger.warning('Error getting image from google because element #rg_s .rg_di was not found.')
                raise IncompatibleUserAgent(self)

        avatar_path = os.path.join(settings.AVATARS_DIR, '%s.png' % self.user.username)
        MIN_RES = 80  # mínima resolución que debe tener cada imagen encontrada, en px
        SEARCH_ATTEMPTS = 3

        g_scrapper = Scrapper(self.user)
        g_scrapper.set_screenshots_dir('google_avatar')
        g_scrapper.open_browser()

        # se queda intentando coger una imágen válida
        attempt_num = 0
        try:
            while True:
                if attempt_num > SEARCH_ATTEMPTS:
                    g_scrapper.logger.warning('Exceeded %i attempts downloading picture profile for bot %s'
                                            % (SEARCH_ATTEMPTS, self.user.username))
                    raise Exception()

                g_scrapper.go_to('http://www.google.com')
                g_scrapper.click(g_scrapper.browser.find_element_by_partial_link_text('Images'))
                img = get_img()
                g_scrapper.click(img)
                g_scrapper.wait_to_page_readystate()
                img_button = g_scrapper.browser.find_element_by_partial_link_text('View image')
                g_scrapper.click(img_button)
                g_scrapper.wait_to_page_readystate()
                g_scrapper.delay.seconds(10)  # para que dé tiempo a cargar la página final con la imágen
                urllib.urlretrieve(g_scrapper.browser.current_url, avatar_path)
                import imghdr
                if imghdr.what(avatar_path):
                    break
                else:
                    os.remove(avatar_path)
                    attempt_num += 1
                    self.logger.warning('Invalid picture downloaded from %s. Trying again (%i)..' %
                                            (g_scrapper.browser.current_url, attempt_num))
                    self.take_screenshot('picture_download_failure_attempt_%i' % attempt_num, force_take=True)

                # try:
                #     PIL.Image.open(avatar_path).close()
                #     break
                # except Exception:
                #     settings.LOGGER.warning('Invalid picture downloaded from %s. Trying again..' % g_scrapper.browser.current_url)

        except (PageNotReadyState,
                NoSuchElementException) as e:
            raise e
        except Exception, e:
            self.logger.exception('Error downloading picture from google')
            g_scrapper.take_screenshot('picture_download_failure')
            raise e
        finally:
            g_scrapper.close_browser()

    def go_to_with_multiple_attempts(self, url, **kwargs):
        if 'n_attempts' in kwargs:
            n_attempts = kwargs['n_attempts']
            kwargs.pop('n_attempts')
        else:
            n_attempts = 3

        attempt = 0
        while True:
            try:
                if attempt >= n_attempts:
                    raise RequestAttemptsExceededException(self, url)
                else:
                    self.go_to(url, **kwargs)
                    break
            except Exception:
                attempt += 1

    def get_quote(self, max_len=160):
        "160 es el limite de caracteres para la bio en twitter por ejemplo"
        def get_quote_from_quotationspage():
            try:
                q_scrapper.go_to('http://www.quotationspage.com/random.php3')

                # a veces se abre ventanita de spam mierda como la última en window_handles, así que vamos pasando
                # desde la última a la primera
                i = -1
                while True:
                    q_scrapper.switch_to_window(i)
                    if q_scrapper.browser.get_window_size()['height'] < 500:
                        i -= 1
                    else:
                        break

                sel_quote = None
                quotes = q_scrapper.get_css_elements('#content dt.quote')
                for q in quotes:
                    if len(q.text) <= max_len:
                        sel_quote = q.text
                        q_scrapper.take_screenshot('quote_get_ok')
                        break
                return sel_quote
            except Exception:
                self.logger.exception('Error getting quote from quotationspage')
                q_scrapper.take_screenshot('quote_get_fail_from_quotationspage')
                return None

        def get_quote_from_quotedb():
            raise NotImplementedError

        q_scrapper = None
        try:
            q_scrapper = Scrapper(self.user)
            q_scrapper.screenshots_dir = 'quotationspage'
            q_scrapper.open_browser()
            sel_quote = get_quote_from_quotationspage()

            if sel_quote:
                return sel_quote
            else:
                raise Exception()
        except Exception, e:
            self.logger.exception('Error getting quote from quotationspage')
            q_scrapper.take_screenshot('quote_get_fail')
            raise e
        finally:
            q_scrapper.close_browser()

    def scroll_to_element(self, element):
        """Scroll element into view"""
        y = element.location['y']
        self.browser.execute_script('window.scrollTo(0, {0})'.format(y))

    def take_screenshot(self, title, force_take=False):
        """toma una captura sólo si se usa phantomjs"""
        try:
            if settings.TAKE_SCREENSHOTS or force_take:
                mkdir_if_not_exists(settings.SCREENSHOTS_DIR)

                # ponemos que la captura cuelgue de la carpeta del usuario en cuestión
                user_dir = os.path.join(settings.SCREENSHOTS_DIR, self.user.real_name + ' - ' + self.user.username)
                mkdir_if_not_exists(user_dir)
                dir = user_dir

                if self.screenshots_dir:
                    dir = os.path.join(dir, self.screenshots_dir)
                    mkdir_if_not_exists(dir)

                screenshot_path = os.path.join(dir, '%i_%s.jpg' % (self.screenshot_num, title))
                self.logger.debug('Taking screenshot: %s' % screenshot_path)
                self.browser.save_screenshot(screenshot_path)
            self.screenshot_num += 1
        except Exception:
            self.logger.exception('Error shooting %i_%s.jpg' % (self.screenshot_num, title))

    def move_mouse_to_el(self, el):
        """Mueve el ratón hacia la coordenada relativa 0,0 de un elemento 'el' dado"""
        # def get_offset(axis):
        #     if self.current_mouse_position[axis] > el.location[axis]:
        #         # si vas de 10 -> 5 se tendrá que mover en -5
        #         return (self.current_mouse_position[axis] - el.location[axis]) * -1
        #     else:
        #         return el.location[axis] - self.current_mouse_position[axis]
        self.delay.during_mousemove()

        if settings.RANDOM_OFFSETS_ON_EL_CLICK:
            x_bound = el.size['width'] - 1  # el límite hasta donde se puede offsetear el click es el ancho
            y_bound = el.size['height'] - 1

            x_offset = random.randint(1, x_bound)
            y_offset = random.randint(1, y_bound)
            ActionChains(self.browser).move_to_element_with_offset(el, x_offset, y_offset).perform()
        else:
            ActionChains(self.browser).move_to_element(el).perform()

    def open_link_in_a_new_window(self, el):
        self.move_mouse_to_el(el)
        self.delay.click_after_move()
        ActionChains(self.browser).context_click(el).perform()
        self.send_special_key(Keys.ARROW_DOWN)
        self.send_special_key(Keys.ARROW_DOWN)
        self.send_special_key(Keys.ENTER)

    def clear_local_storage(self):
        # para que no aparezcan cositas de otras instancias de phantomjs
        self.browser.execute_script('localStorage.clear();')

    def dump_page_source(self):
        with open(os.path.join(settings.BASE_DIR, 'core', 'scrapper', 'page_source.html'), 'w') as f:
            f.write(self.browser.page_source.encode('utf-8'))

    def get_random_reply(self, max_words=3,
                         exclamation_percent=20, point_percent=20,
                         mayus_percent=20):
        """Devuelve una cadena formada por entre 1 y 3 palabras"""

        def do(percent):
            """Dice si se hace algo según la probabilidad de que ocurra"""
            return random.randrange(100) < percent

        def format_word(w):
            f_word = w
            if do(exclamation_percent):
                f_word += '!' * random.randint(1, 3)
            elif do(point_percent):
                f_word += '.' * random.randint(1, 3)

            # el resultado lo ponemos en mayus-minusc según caiga
            if do(mayus_percent):
                f_word = f_word.upper()
            else:
                f_word = f_word.lower()

            return f_word

        def chose_word():
            """Escoje una palabra al azar dentro del grupo escogido entre los grupos 'all' y del
            lenguaje elegido previamente"""

            # hay un 80% de probabilidad de que el grupo sea el del lenguaje y un 20% para el genérico
            ALL_GROUP_WEIGHT = 0.2
            LANG_GROUP_WEIGHT = 0.8

            group = numpy.random.choice(
                [settings.REPLY_MSGS['all'], settings.REPLY_MSGS[lang_chosen]],
                p=[ALL_GROUP_WEIGHT, LANG_GROUP_WEIGHT]
            )

            return random.choice(group)

        words = []

        num_words = random.randint(1, max_words)
        lang_chosen = random.choice(['en', 'es'])

        while not num_words == len(words):
            word = chose_word()
            if word not in words:
                words.append(word)

        # aplicamos ! .. etc
        for i, word in enumerate(words):
            words[i] = format_word(word)

        return ' '.join(words)


class ScrapperLogger(object):
    def __init__(self, scrapper):
        if not settings.LOGGER:
            settings.set_logger('default')
            settings.LOGGER.warning('No logger configured, default logger created')

        self.logger = settings.LOGGER
        if scrapper.user:
            if scrapper.user.pk:
                self.scrapper_id = '[%s | %i]' % (scrapper.user.username, scrapper.user.id)
            else:
                self.scrapper_id = '[%s]' % scrapper.user.username
        else:
            self.scrapper_id = '[no-user]'

    def info(self, msg):
        self.logger.info('%s - %s' % (self.scrapper_id, msg))

    def debug(self, msg):
        self.logger.debug('%s - %s' % (self.scrapper_id, msg))

    def warning(self, msg):
        self.logger.warning('%s - %s' % (self.scrapper_id, msg))

    def error(self, msg):
        self.logger.error('%s - %s' % (self.scrapper_id, msg))

    def exception(self, msg):
        self.logger.exception('%s - %s' % (self.scrapper_id, msg))


class MyActionChains(ActionChains):
    pass