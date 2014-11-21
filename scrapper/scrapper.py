# -*- coding: utf-8 -*-

import sys
import urllib
from selenium.common.exceptions import NoSuchFrameException, TimeoutException
from selenium.webdriver import ActionChains, DesiredCapabilities, Proxy
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from stem import Signal
from stem.control import Controller
from selenium import webdriver
import socket
import telnetlib
from .delay import Delay
from .exceptions import RequestAttemptsExceededException, ProxyConnectionError, ProxyTimeoutError, \
    InternetConnectionError, ProxyUrlRequestError
from .logger import get_browser_instance_id
import my_phantomjs_webdriver
from project.models import ProxiesGroup
from utils import *
from twitter_bots import settings

INVALID_EMAIL_DOMAIN_MSG = 'Invalid email domain used, only accepts: hushmail.com, gmail.com, hotmail.com'


class Scrapper(object):
    # cada scrapper (hotmail, twitter..) tendrá su propia carpeta para capturar los pantallazos
    screenshots_dir = ''
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
        if self.user.pk:
            self.browser_id = get_browser_instance_id(self.user)

    def check_proxy_works_ok(self):
        """Mira si funciona correctamente el proxy que se supone que tenemos contratado"""
        self.go_to('http://twitter.com')

    def set_screenshots_dir(self, dir_name):
        self.screenshots_dir = dir_name
        self.screenshot_num = 1

    def open_browser(self, renew_user_agent=False):
        """Devuelve el navegador a usar"""

        def renew_tor_ip(method='stem'):
            """
            Usa la librería stem para renovar ip con la que se conecta a tor
            Para que esto funcione hay que editar /usr/local/etc/tor/torrc y añadir la línea:
            ControlPort 9051
            """
            if method == 'stem':
                with Controller.from_port(port=settings.TOR_CTRL_PORT) as controller:
                    controller.authenticate()
                    controller.signal(Signal.NEWNYM)
            elif method == 'socket':
                try:
                    tor_c = socket.create_connection(("127.0.0.1", settings.TOR_CTRL_PORT))
                    tor_c.send('AUTHENTICATE\r\nSIGNAL NEWNYM\r\n')
                    response = tor_c.recv(1024)
                    if response != '250 OK\r\n250 OK\r\n':
                        settings.LOGGER.warning('Unexpected response from Tor control port: {}\n'.format(response))
                except Exception, e:
                    settings.LOGGER.warning('Error connecting to Tor control port: {}'.format(repr(e)))
            elif method == 'telnet':
                telnet = telnetlib.Telnet("127.0.0.1", settings.TOR_CTRL_PORT)
                telnet.set_debuglevel(0)
                telnet.write('authenticate ""' + "\n")
                telnet.read_until("250 OK")
                telnet.write("signal newnym" + "\n")
                telnet.read_until("250 OK")
                telnet.write("quit")

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
                    '--cookies-file=%s' % os.path.join(settings.PHANTOMJS_COOKIES_DIR, '%i.txt' % self.user.id),
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
                desired_capabilities=dcap
            )

            # self.browser = webdriver.PhantomJS(
            #     settings.PHANTOMJS_BIN_PATH,
            #     service_args=service_args,
            #     desired_capabilities=dcap
            # )
            settings.LOGGER.debug('%s phantomJS instance opened successfully' % get_browser_instance_id(self.user))

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
            if self.user.proxy_for_usage:
                # si ya estaba usando un proxy comprobamos si el proxy aún sigue en los txts, si no se le asigna uno de los nuevos SIEMPRE QUE
                # el bot no haya sido suspendido
                if not self.user.proxy_for_usage.is_in_proxies_txts:
                    settings.LOGGER.info('Proxy %s for bot %s is no longer on txts. Trying to assign new one..' %
                                         (self.user.proxy_for_usage.__unicode__(), self.user.__unicode__()))
                    self.user.assign_proxy()
            else:
                # si no tiene proxy se le asigna uno
                self.user.assign_proxy()

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

        # cargamos las cookies que el usuario haya guardado (no se puede hacer si no se entra a la página del dominio de cada cookie)
        # cookies = simplejson.loads(self.user.cookies)
        # for cookie in cookies:
        #     self.browser.add_cookie(cookie)

    def close_browser(self):
        try:
            self.browser.quit()
            settings.LOGGER.debug('%s %s instance closed sucessfully' % (get_browser_instance_id(self.user), self.user.get_webdriver()))
        except Exception as ex:
            if not self.browser:
                settings.LOGGER.warning('%s %s instance was not opened browser' % (get_browser_instance_id(self.user), self.user.get_webdriver()))
            else:
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
            if 'timeout' in kwargs:
                try:
                    self.wait_visibility_of_css_element(el, **kwargs)
                    return True
                except Exception:
                    return False
            else:
                return not self.check_invisibility(el, **kwargs)

        def is_visible_obj():
            "Mira a partir del obj 'el' pasado por parámetro"
            if 'timeout' in kwargs:
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

    def wait_to_page_loaded(self):
        wait_condition(lambda: self.browser.execute_script("return document.readyState;") == 'complete', timeout=200)
        self.take_screenshot('page_loaded')

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

    def go_to(self, url, timeout=None, wait_page_loaded=False, ignore_timeout_error=False):

        def proxy_works():
            """Para ver que el proxy funciona comprobamos contra google"""
            scr = Scrapper(self.user)
            scr.open_browser()
            prev_url = scr.browser.current_url
            scr.browser.get('http://google.com')
            return scr.browser.current_url != prev_url

        def internet_connection_works():
            """Para ver que la conexión a internet funciona lanzamos el phantom sin ir a través de proxy"""
            browser = webdriver.PhantomJS(settings.PHANTOMJS_BIN_PATH)
            prev_url = browser.current_url
            browser.get('http://google.com')
            return browser.current_url != prev_url

        try:
            if timeout:
                self.browser.set_page_load_timeout(timeout)
            prev_url = self.browser.current_url
            self.browser.get(url)
            # self.browser.get('http://localhost:8001/admin/')
            is_new_url = url != prev_url
            if is_new_url:
                if self.browser.current_url != prev_url:
                    # si ha cambiado current_url es que se tomó bien la nueva
                    if wait_page_loaded:
                        self.wait_to_page_loaded()
                    self.check_user_agent_compatibility()
                    self._quit_focus_from_address_bar()
                    settings.LOGGER.debug('%s go_to: %s' % (self.browser_id, url))
                    self.take_screenshot('go_to')
                else:
                    if proxy_works():
                        # si el proxy funciona es que el fallo es específico de pedir esa url en concreto
                        raise ProxyUrlRequestError(self, url)
                    else:
                        if internet_connection_works():
                            # si el proxy no funciona y sí la conexión a internet, es culpa del proxy
                            raise ProxyConnectionError(self)
                        else:
                            raise InternetConnectionError()
        except TimeoutException:
            if ignore_timeout_error:
                settings.LOGGER.warning('%s Timeout loading url %s, ignoring TimeoutException..' %
                                        (get_browser_instance_id(self.user), url))
        except Exception, e:
            raise e
        finally:
            if timeout:
                self.browser.set_page_load_timeout(settings.PAGE_LOAD_TIMEOUT)

    def check_user_agent_compatibility(self):
        """Dice si el user agent usado es de móvil o no compatible"""
        if check_condition(lambda : 'mobile' in self.browser.current_url):
            self.change_user_agent()
            self.open_browser()

    def change_user_agent(self):
        self.user.user_agent = generate_random_desktop_user_agent()
        self.user.save()
        settings.LOGGER.info('Setted user_agent for bot %s' % self.user.username)

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

        if settings.RANDOM_OFFSETS_ON_EL_CLICK:
            x_bound = el.size['width'] - 1  # el límite hasta donde se puede offsetear el click es el ancho
            y_bound = el.size['height'] - 1

            x_offset = random.randint(1, x_bound)
            y_offset = random.randint(1, y_bound)
            ActionChains(self.browser).move_to_element_with_offset(el, x_offset, y_offset).click().perform()
        else:
            ActionChains(self.browser).move_to_element(el).click().perform()

        self.delay.box_switch()

        # si el es un selector css entonces hacemos captura de pantalla cómo queda después del click
        if el_str:
            msg = '%s click_%s' % (get_browser_instance_id(self.user), el_str)
            self.take_screenshot(msg)
            settings.LOGGER.debug(msg)

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

    def download_pic_from_google(self):
        """Pilla de google una imágen y la guarda en disco"""
        def get_img():
            "Devuelve la imágen de la lista de resultados sobre la que luego haremos click para descargarla"
            g_scrapper.fill_input_text(
                'input[name="q"]',
                names.get_full_name(gender=self.user.get_gender_display())
            )
            g_scrapper.send_special_key(Keys.ENTER)
            g_scrapper.wait_to_page_loaded()
            self.delay.seconds(3)

            if self.check_visibility('#rg_s .rg_di'):
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
                settings.LOGGER.exception()
                raise Exception()

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
                    settings.LOGGER.warning('Exceeded %i attempts downloading picture profile for bot %s'
                                            % (SEARCH_ATTEMPTS, self.user.username))
                    raise Exception()

                g_scrapper.go_to('http://www.google.com')
                g_scrapper.click(g_scrapper.browser.find_element_by_partial_link_text('Images'))
                img = get_img()
                g_scrapper.click(img)
                g_scrapper.wait_to_page_loaded()
                img_button = g_scrapper.browser.find_element_by_partial_link_text('View image')
                g_scrapper.click(img_button)
                g_scrapper.wait_to_page_loaded()
                g_scrapper.delay.seconds(10)  # para que dé tiempo a cargar la página final con la imágen
                urllib.urlretrieve(g_scrapper.browser.current_url, avatar_path)
                import imghdr
                if imghdr.what(avatar_path):
                    break
                else:
                    os.remove(avatar_path)
                    attempt_num += 1
                    settings.LOGGER.warning('Invalid picture downloaded from %s. Trying again (%i)..' %
                                            (g_scrapper.browser.current_url, attempt_num))
                    self.take_screenshot('picture_download_failure_attempt_%i' % attempt_num, force_take=True)

                # try:
                #     PIL.Image.open(avatar_path).close()
                #     break
                # except Exception:
                #     settings.LOGGER.warning('Invalid picture downloaded from %s. Trying again..' % g_scrapper.browser.current_url)

        except Exception, e:
            settings.LOGGER.exception('%s Could not download picture from google for user "%s"' %
                             (get_browser_instance_id(self.user), self.user.username))
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
                    raise RequestAttemptsExceededException(self.user, url)
                else:
                    self.go_to(url, **kwargs)
                    break
            except Exception:
                attempt += 1

    def get_quote(self, max_len=160):
        "160 es el limite de caracteres para la bio en twitter por ejemplo"
        def get_quote_from_quotationspage():
            try:
                q_scrapper.go_to('http://www.quotationspage.com/random.php3', ignore_timeout_error=True)

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
                settings.LOGGER.exception('Error getting quote from quotationspage')
                q_scrapper.take_screenshot('quote_get_fail')
                return None

        def get_quote_from_quotedb():
            pass

        q_scrapper = None
        try:
            q_scrapper = Scrapper(self.user)
            q_scrapper.screenshots_dir = 'quotationspage'
            q_scrapper.open_browser()
            sel_quote = get_quote_from_quotationspage()
            if not sel_quote:
                sel_quote = get_quote_from_quotedb()

            if sel_quote:
                return sel_quote
            else:
                raise Exception()
        except Exception, e:
            settings.LOGGER.exception('%s Error getting quote' % get_browser_instance_id(self.user))
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
                user_dir = os.path.join(settings.SCREENSHOTS_DIR, self.user.real_name)
                mkdir_if_not_exists(user_dir)

                dir = user_dir

                if self.screenshots_dir:
                    dir = os.path.join(dir, self.screenshots_dir)
                    mkdir_if_not_exists(dir)

                self.browser.save_screenshot(os.path.join(dir, '%i_%s.jpg' % (self.screenshot_num, title)))
            self.screenshot_num += 1
        except Exception:
            settings.LOGGER.exception('%s Error shooting %i_%s.jpg' %
                             (get_browser_instance_id(self.user), self.screenshot_num, title))

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


class MyActionChains(ActionChains):
    pass