"""
Selenium-краулер: многопоточный обход с пулом браузеров.

- По умолчанию 4 потока; у каждого воркера СВОЙ экземпляр браузера
  (браузер не потокобезопасен — один драйвер на поток обязателен).
- Ротация браузеров (--rotate-browsers): воркеры получают Chrome и Firefox
  по очереди — у страниц разные отпечатки движков (Blink/Gecko).
- Прокси (--proxy / PROXY в config.env): ВАЖНО — браузеры не умеют прокси
  с логином/паролем через флаг. Используй host:port (IP-whitelist на прокси)
  или локальный туннель: ssh -L 3128:127.0.0.1:3128 root@<vps> → --proxy http://127.0.0.1:3128
"""

import itertools
import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

# Загружаем config.env из configs/crawler-selenium/
CONFIG_DIR = Path(__file__).parents[2] / "configs" / "crawler-selenium"
load_dotenv(CONFIG_DIR / "config.env")

BROWSERS = ("chrome", "firefox")


def _proxy_parts(proxy):
    """Разбирает proxy-URL в (scheme, host, port). Auth браузеры через флаг не умеют."""
    p = urlparse(proxy if "://" in proxy else f"http://{proxy}")
    if p.username or p.password:
        print("[WARN] Прокси с логином/паролем браузер не поддерживает — "
              "нужен IP-whitelist или ssh-туннель (см. README). Использую host:port.")
    scheme = p.scheme if p.scheme in ("http", "socks5", "socks4") else "http"
    return scheme, p.hostname, p.port or 3128


def init_driver(browser="chrome", headless=True, user_agent=None, proxy=None):
    """Инициализирует WebDriver (chrome | firefox)."""
    if browser == "firefox":
        opts = FirefoxOptions()
        if headless:
            opts.add_argument("-headless")
        if user_agent:
            opts.set_preference("general.useragent.override", user_agent)
        if proxy:
            scheme, host, port = _proxy_parts(proxy)
            opts.set_preference("network.proxy.type", 1)
            if scheme.startswith("socks"):
                opts.set_preference("network.proxy.socks", host)
                opts.set_preference("network.proxy.socks_port", port)
                opts.set_preference("network.proxy.socks_version", 5)
            else:
                for kind in ("http", "ssl"):
                    opts.set_preference(f"network.proxy.{kind}", host)
                    opts.set_preference(f"network.proxy.{kind}_port", port)
        driver = webdriver.Firefox(
            service=FirefoxService(GeckoDriverManager().install()), options=opts)
    else:
        opts = ChromeOptions()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1920,1080")
        # Изолированный профиль во временной папке: краулерный Chrome не трогает
        # твой рабочий браузер (его вкладки, профиль). Папка чистится в quit_all().
        udd = tempfile.mkdtemp(prefix="crawler-chrome-")
        opts.add_argument(f"--user-data-dir={udd}")
        opts.add_argument("--profile-directory=Default")
        if user_agent:
            opts.add_argument(f"--user-agent={user_agent}")
        if proxy:
            scheme, host, port = _proxy_parts(proxy)
            opts.add_argument(f"--proxy-server={scheme}://{host}:{port}")
        # Скрываем автоматизацию
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        # perf-лог CDP: из него достаём заголовки ответа (X-Robots-Tag) — браузер
        # их напрямую не отдаёт, а для индексируемости они нужны.
        opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()), options=opts)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        })
        driver._crawler_udd = udd          # временный профиль — удалим при закрытии
    driver.set_page_load_timeout(60)
    return driver


def _get_with_retries(driver, url, retries=3):
    """driver.get с ретраями на таймаут/сбой рендерера (пауза 2с, 4с, 6с…).
    Если после всех попыток страница всё же открылась частично — вернём DOM."""
    for attempt in range(1, retries + 1):
        try:
            driver.get(url)
            return
        except (TimeoutException, WebDriverException) as e:
            msg = str(e).splitlines()[0]
            if attempt < retries:
                print(f"  [WARN] {url}: {msg} — повтор {attempt}/{retries - 1}")
                time.sleep(2 * attempt)
            else:
                print(f"  [WARN] {url}: {msg} — беру DOM как есть после {retries} попыток")


def response_headers(driver):
    """Заголовки ответа главного документа из CDP perf-лога (нижний регистр ключей).
    Нужно ради X-Robots-Tag, который браузер напрямую не отдаёт. Firefox: пусто."""
    try:
        logs = driver.get_log("performance")
    except Exception:
        return {}
    headers = {}
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
        except (KeyError, ValueError):
            continue
        params = msg.get("params", {})
        if msg.get("method") == "Network.responseReceived" and params.get("type") == "Document":
            headers = params["response"].get("headers", {})   # последний Document = главный
    return {k.lower(): v for k, v in headers.items()}


def crawl_page(driver, url, wait_time=3, retries=3):
    """Загружает страницу и ждёт выполнения JavaScript (с ретраями)."""
    _get_with_retries(driver, url, retries)
    time.sleep(wait_time)
    return driver.page_source


def crawl_with_scroll(driver, url, scrolls=3, wait_time=2, retries=3):
    """Загружает страницу и прокручивает вниз (бесконечная лента, lazy-load)."""
    _get_with_retries(driver, url, retries)
    time.sleep(wait_time)
    for i in range(scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time)
        print(f"  [SCROLL] {i + 1}/{scrolls}")
    return driver.page_source


class DriverPool:
    """Один драйвер на поток-воркер. С --rotate-browsers воркеры
    получают Chrome/Firefox по очереди."""

    def __init__(self, headless=True, rotate_browsers=False, proxy=None):
        self.headless = headless
        self.rotate = rotate_browsers
        self.proxy = proxy
        self._tls = threading.local()
        self._counter = itertools.count()
        self._all = []
        self._lock = threading.Lock()

    def get(self):
        d = getattr(self._tls, "driver", None)
        if d is None:
            n = next(self._counter)
            browser = BROWSERS[n % len(BROWSERS)] if self.rotate else "chrome"
            print(f"  [DRIVER] воркер {n + 1}: {browser}")
            d = init_driver(browser=browser, headless=self.headless, proxy=self.proxy)
            self._tls.driver = d
            with self._lock:
                self._all.append(d)
        return d

    def quit_all(self):
        for d in self._all:
            udd = getattr(d, "_crawler_udd", None)
            try:
                d.quit()
            except Exception:
                pass
            if udd:                         # чистим временный профиль Chrome
                shutil.rmtree(udd, ignore_errors=True)
