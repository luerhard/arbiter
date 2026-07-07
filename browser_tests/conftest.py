"""Host-run browser smoke tests for the expert decision app.

These run OUTSIDE the docker test suite (the app containers are Alpine and
ship no browser). They drive the local dev stack at http://localhost:8000
with headless Firefox via the system geckodriver.

Run:
    uvx --with selenium --with pytest pytest browser_tests/ -q

Requires: firefox + geckodriver on the host, `docker compose up` running,
and the populated dev database (expert1/123, Populism batch in expert phase).
"""

import os

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = os.environ.get("APP_URL", "http://localhost:8000")
USERNAME = os.environ.get("APP_USER", "expert1")
PASSWORD = os.environ.get("APP_PASSWORD", "123")
EXPERT_BATCH_ID = int(os.environ.get("APP_EXPERT_BATCH", "3"))


@pytest.fixture(scope="session")
def driver():
    options = Options()
    options.add_argument("-headless")
    drv = webdriver.Firefox(options=options)
    drv.set_window_size(1400, 1000)
    yield drv
    drv.quit()


@pytest.fixture(scope="session")
def expert_session(driver):
    """Log in once and navigate to the expert batch entry point."""
    driver.get(f"{BASE_URL}/users/login/")
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(
        By.CSS_SELECTOR, "form button[type=submit], form input[type=submit]"
    ).click()
    WebDriverWait(driver, 10).until(lambda d: "/login" not in d.current_url)

    driver.get(f"{BASE_URL}/expert/batch/{EXPERT_BATCH_ID}")
    WebDriverWait(driver, 10).until(lambda d: "/assignment/" in d.current_url)
    return driver
