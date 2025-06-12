import threading
import time
import random
from PIL import Image, ImageDraw

thread_safe_display = None
fonts = None
exit_cb = None

running = False
update_thread = None
start_time = 0
progress = 0
code_lines = []


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global running, update_thread, start_time, progress, code_lines
    running = True
    start_time = time.time()
    progress = 0
    code_lines = []
    update_thread = threading.Thread(target=_loop, daemon=True)
    update_thread.start()


def handle_input(pin):
    if pin == "KEY3":
        stop()


def stop():
    global running
    running = False
    if update_thread:
        update_thread.join()
    exit_cb()


def _loop():
    global progress, code_lines, running
    while running and time.time() - start_time < 15:
        progress = min(100, progress + random.randint(1, 4))
        code_lines.append(_gen_line())
        if len(code_lines) > 5:
            code_lines.pop(0)
        _draw()
        time.sleep(0.3)
    if running:
        # Ended naturally after 15 seconds
        running = False
        exit_cb()


def _gen_line():
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(chars) for _ in range(16))


def _draw():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    d.text((5, 5), "HACKING...", font=fonts[1], fill=(0, 255, 0))
    bar_x, bar_y, bar_w, bar_h = 5, 25, 118, 10
    d.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], outline=(0, 255, 0))
    fill_w = int(bar_w * progress / 100)
    d.rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], fill=(0, 255, 0))
    d.text((bar_x, bar_y + 12), f"{progress:3d}%", font=fonts[0], fill=(0, 255, 0))
    y = bar_y + 28
    for line in code_lines:
        d.text((5, y), line, font=fonts[0], fill=(0, 255, 0))
        y += 12
    d.text((5, 115), "Press 3 to exit", font=fonts[0], fill=(255, 255, 0))
    thread_safe_display(img)
