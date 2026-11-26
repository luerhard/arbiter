"""Take the screenshots of the documentation from the local dev server.

Run it on the host (the app containers ship no browser), with the dev stack up:

    uv run --with playwright python docs/screenshots/shoot.py           # every page
    uv run --with playwright python docs/screenshots/shoot.py discuss   # some pages

Before each page, the demo data is rebuilt in the stage the page needs (manage.py demodata
--stage ..., run through `docker compose exec`). That replaces the two demo projects and resets
the three demo accounts in the dev database, and touches nothing else. The pictures are taken
in light mode at twice the resolution and written next to this file.

It uses the system's Chromium (CHROMIUM, default /usr/bin/chromium-browser). Without one, run
`uv run --with playwright playwright install chromium` once and set CHROMIUM to "".
"""

import os
from pathlib import Path
import subprocess
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("APP_URL", "http://localhost:8000")
CHROMIUM = os.environ.get("CHROMIUM", "/usr/bin/chromium-browser") or None
OUT = Path(__file__).parent
PASSWORD = "demo"  # the demo accounts' password, see core/projects/management/commands/demodata.py
CLASSIFICATION, SPANS = "Populist Communication", "Offensive Language"

# light mode, and the dev server's debug toolbar out of the picture (and out of the way of clicks)
INIT = """
localStorage.setItem('theme', 'light');
document.addEventListener('DOMContentLoaded', () => {
  const style = document.createElement('style');
  style.textContent = '#djDebug { display: none !important; }';
  document.head.appendChild(style);
});
"""


def demodata(stage):
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "web",
            "python",
            "manage.py",
            "demodata",
            "--stage",
            stage,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def new_page(browser, username=None, height=800):
    context = browser.new_context(
        viewport={"width": 1280, "height": height},
        device_scale_factor=2,
        color_scheme="light",
    )
    context.add_init_script(INIT)
    page = context.new_page()
    if username:
        page.goto(f"{BASE}/users/login/")
        page.fill("#username", username)
        page.fill("#password", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_url(f"{BASE}/")
    return page


def shot(page, name):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)  # transitions
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.mouse.move(0, 0)
    page.screenshot(path=str(OUT / f"{name}.png"))
    print(f"  {name}.png")


def task_url(page, project):
    """The link of the project's card under 'Waiting for you' on the home page."""
    page.goto(f"{BASE}/")
    card = page.locator("article.card", has_text=project)
    return BASE + card.locator("a.btn").get_attribute("href")


def mark(page, phrase, key, within="body"):
    """In the span editor: drag over the words of phrase, then press the label's key. within:
    the editor's container, where the page shows the text more than once."""
    editor = page.locator(within)
    words = [w.strip(",.!") for w in editor.locator("[data-i]").all_inner_texts()]
    target = [w.strip(",.!") for w in phrase.split()]
    start = next(i for i in range(len(words)) if words[i : i + len(target)] == target)
    first = editor.locator(f'[data-i="{start}"]').bounding_box()
    last = editor.locator(f'[data-i="{start + len(target) - 1}"]').bounding_box()
    page.mouse.move(first["x"] + 2, first["y"] + first["height"] / 2)
    page.mouse.down()
    page.mouse.move(last["x"] + last["width"] - 2, last["y"] + last["height"] / 2, steps=5)
    page.mouse.up()
    page.keyboard.press(key)


def close_codebook(page):
    """Close the codebook panel if it is open (the page remembers it for the next one)."""
    page.wait_for_timeout(300)
    close = page.get_by_role("button", name="Close Codebook")
    if close.is_visible():
        close.click()
        page.wait_for_timeout(800)  # the panel slides out, the page takes the room


def say(page, text):
    page.fill("#message-input", text)
    page.press("#message-input", "Enter")
    page.wait_for_timeout(300)


# --- one function per page of the documentation ---------------------------------------------


def signin(browser):
    demodata("annotation")
    page = new_page(browser)
    page.goto(f"{BASE}/users/login/")
    shot(page, "login")

    page = new_page(browser, "anna.berger")
    page.goto(f"{BASE}/users/profile/")
    shot(page, "profile")


def annotate(browser):
    demodata("annotation")
    anna = new_page(browser, "anna.berger")
    shot(anna, "annotator_start")

    # Anna's first open text is the 4th; the 5th asks for a referendum: Popular sovereignty
    anna.goto(task_url(anna, CLASSIFICATION))
    anna.get_by_role("button", name="Next sample").click()
    anna.get_by_text("Sample 5 of 10").wait_for()
    anna.keyboard.press("3")
    shot(anna, "annotator_annotation_interface")

    anna.goto(task_url(anna, SPANS))
    close_codebook(anna)
    mark(anna, "complete idiot", "1")
    mark(anna, "damn", "3")
    mark(anna, "had better watch out on their way home", "2")
    shot(anna, "annotator_span_annotation")

    tom = new_page(browser, "tom.keller")  # Tom has labeled every text
    tom.goto(task_url(tom, CLASSIFICATION))
    shot(tom, "annotator_finalize_annotation")


def discuss(browser):
    demodata("discussion")
    anna = new_page(browser, "anna.berger", height=900)
    url = task_url(anna, CLASSIFICATION)

    # alone in the room: the discussion waits for Tom
    anna.goto(url)
    anna.get_by_text("Waiting for tom.keller to join").wait_for()
    close_codebook(anna)
    shot(anna, "discussion_waiting")

    # Tom joins; the first disagreement opens and they talk it through
    tom = new_page(browser, "tom.keller")
    tom.goto(url)
    anna.get_by_text("Disagreement 1 of").wait_for()
    say(anna, "'Unelected judges' sounds like an elite to me.")
    say(tom, "It's a court, an institution. The point is who decides.")
    say(anna, "Fair enough, it is about who has the last word. I'll take anti-elitism out.")
    say(tom, "Saved, see you on the next one.")
    tom.get_by_role("button", name="Save my label").click()
    # Anna removes Anti-elitism from her label after discussing, but has not saved yet
    anna.locator("#current-labels").get_by_text("Anti-elitism").click()
    anna.get_by_text("tom.keller has saved").wait_for()
    anna.evaluate("window.scrollTo(0, 0)")
    shot(anna, "annotator_discussion_interface")

    # the span project: was the insult "complete idiot" or only "idiot"?
    url = task_url(anna, SPANS)
    anna.goto(url)
    tom.goto(url)
    anna.get_by_text("Disagreement 1 of").wait_for()
    close_codebook(anna)
    say(tom, "I only marked 'idiot'. 'complete' makes it stronger, but it is not the insult.")
    say(anna, "The codebook says to mark the words that carry it. That is 'idiot', you're right.")
    tom.get_by_role("button", name="Save my spans").click()
    # Anna shortens her insult to the word itself, but has not saved yet
    current = anna.locator("#current-spans")
    current.locator("li", has_text="complete idiot").get_by_role("button", name="Remove").click()
    mark(anna, "idiot", "1", within="#current-spans")
    anna.get_by_text("tom.keller has saved").wait_for()
    anna.set_viewport_size({"width": 1280, "height": 1180})  # down to the Save button
    anna.evaluate("window.scrollTo(0, 0)")
    shot(anna, "annotator_discussion_spans")


PAGES = {"signin": signin, "annotate": annotate, "discuss": discuss}

if __name__ == "__main__":
    chosen = sys.argv[1:] or list(PAGES)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        for name in chosen:
            print(name)
            PAGES[name](browser)
        browser.close()
