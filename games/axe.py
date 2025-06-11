import asyncio
import threading
from io import BytesIO
from PIL import Image
import pyppeteer

SCREEN_W = 128
SCREEN_H = 128
URL = "https://paulthomason.github.io/axe/"

thread_safe_display = None
fonts = None
exit_cb = None

browser = None
page = None
loop = None
running = False
update_task = None


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global loop, running
    running = True
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    asyncio.run_coroutine_threadsafe(_launch(), loop)


def _ensure_task(coro):
    if loop:
        return asyncio.run_coroutine_threadsafe(coro, loop)


async def _launch():
    global browser, page, update_task
    browser = await pyppeteer.launch(headless=True, args=["--no-sandbox"])
    page = await browser.newPage()
    await page.setViewport({"width": 800, "height": 600})
    await page.goto(URL)
    update_task = asyncio.create_task(_update_loop())


async def _update_loop():
    while running:
        await _draw_page()
        await asyncio.sleep(0.1)


async def _draw_page():
    if not page:
        return
    data = await page.screenshot(fullPage=False)
    img = Image.open(BytesIO(data)).resize((SCREEN_W, SCREEN_H))
    thread_safe_display(img)


def handle_input(pin):
    if pin == "KEY1":
        _ensure_task(page.keyboard.press(" "))
    elif pin == "KEY2":
        stop()


def stop():
    global running
    running = False
    _ensure_task(_shutdown())


async def _shutdown():
    global browser
    if update_task:
        update_task.cancel()
    if browser:
        await browser.close()
    exit_cb()

