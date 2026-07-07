"""Browser smoke tests for the redesigned expert decision app.

Kept deliberately non-destructive: they create and undo codebook drafts and
toggle UI state, but never submit a decision.
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

MARKER = "BROWSER-SMOKE-TEST edge case"


def _wait(driver, condition, timeout=10):
    return WebDriverWait(driver, timeout).until(condition)


def _panel_html(driver):
    # Scope assertions to the panel: in dev mode the debug toolbar dumps the
    # render context into the page, so page_source contains stale content.
    return driver.find_element(By.ID, "codebook-panel").get_attribute("innerHTML")


def _open_codebook_editor(driver):
    driver.find_element(By.ID, "edit-button").click()
    return _wait(driver, lambda d: d.find_elements(By.ID, "codebook-content"))[0]


def test_codebook_draft_survives_reload(expert_session):
    driver = expert_session
    assignment_url = driver.current_url

    textarea = _open_codebook_editor(driver)
    textarea.send_keys(f"\n## {MARKER}\n")
    driver.find_element(By.ID, "rationale").send_keys("browser smoke test")
    driver.find_element(By.ID, "draft-save-button").click()

    # Panel swaps back to view mode showing the draft indicator.
    _wait(driver, lambda d: "Uncommitted draft" in _panel_html(d))

    # Full reload: the draft must come back from the server, not the DOM.
    driver.get(assignment_url)
    _wait(driver, lambda d: "Uncommitted draft" in _panel_html(d))
    assert MARKER in _panel_html(driver)

    # Undo restores the committed codebook.
    driver.find_element(By.ID, "draft-undo-button").click()
    _wait(driver, lambda d: d.switch_to.alert is not None)
    driver.switch_to.alert.accept()
    _wait(driver, lambda d: "Uncommitted draft" not in _panel_html(d))
    assert MARKER not in _panel_html(driver)


def test_codebook_editor_cancel_returns_to_view(expert_session):
    driver = expert_session
    driver.get(driver.current_url)
    _open_codebook_editor(driver)

    driver.find_element(By.ID, "draft-cancel-button").click()
    _wait(driver, lambda d: d.find_elements(By.ID, "edit-button"))
    assert not driver.find_elements(By.ID, "codebook-content")


def test_label_chips_toggle_checkbox_state(expert_session):
    driver = expert_session
    driver.get(driver.current_url)

    # Reach a label form: open assignments show it directly; completed ones
    # need the explicit edit flow.
    if "Edit decision" in driver.page_source:
        driver.find_element(
            By.XPATH,
            "//button[contains(., 'Edit decision')]",
        ).click()
    checkbox = _wait(
        driver,
        lambda d: d.find_elements(By.CSS_SELECTOR, "#expert-form input[name='labels']"),
    )[0]

    before = checkbox.is_selected()
    label_for = driver.find_element(
        By.CSS_SELECTOR,
        f"label[for='{checkbox.get_attribute('id')}']",
    )
    label_for.click()
    _wait(driver, lambda d: checkbox.is_selected() != before)
    # Toggle back; nothing is submitted.
    label_for.click()
    _wait(driver, lambda d: checkbox.is_selected() == before)
