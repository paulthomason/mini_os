import threading
import time
import random
from PIL import Image, ImageDraw

SCREEN_W = 128
SCREEN_H = 128

# Target radii based on canvas size. The game now centers a much larger target
# so the radii are increased compared to the original values.
BASE = min(SCREEN_W, SCREEN_H)
TARGET_RADIUS_OUTERMOST = int(BASE * 0.4)
TARGET_RADIUS_OUTER = int(BASE * 0.3)
TARGET_RADIUS_MIDDLE = int(BASE * 0.2)
TARGET_RADIUS_INNER = int(BASE * 0.1)

# Slider lengths are derived from the new target size
AIM_SLIDER_LENGTH = TARGET_RADIUS_OUTERMOST * 2
POWER_SLIDER_LENGTH = TARGET_RADIUS_OUTERMOST * 2

STATE_AIM_H = 0
STATE_AIM_V = 1
STATE_AIM_P = 2
STATE_THROW = 3
STATE_RESULT = 4

thread_safe_display = None
fonts = None
exit_cb = None

state = STATE_AIM_H
h_pos = 0.0
v_pos = 0.0
p_pos = 0.0
h_dir = 1
v_dir = 1
p_dir = 1

running = False
update_thread = None
result_text = ""


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global running, state, h_pos, v_pos, p_pos, h_dir, v_dir, p_dir
    running = True
    state = STATE_AIM_H
    h_pos = v_pos = p_pos = 0.0
    h_dir = v_dir = p_dir = 1
    start_thread()


def start_thread():
    global update_thread
    update_thread = threading.Thread(target=game_loop, daemon=True)
    update_thread.start()


def stop():
    global running
    running = False
    if update_thread:
        update_thread.join()
    exit_cb()


def handle_input(pin):
    global state, h_dir, v_dir, p_dir, result_text
    if pin == "KEY2":
        stop()
        return
    if state in (STATE_AIM_H, STATE_AIM_V, STATE_AIM_P) and pin == "KEY1":
        if state == STATE_AIM_H:
            state = STATE_AIM_V
        elif state == STATE_AIM_V:
            state = STATE_AIM_P
        else:
            state = STATE_THROW
    elif state == STATE_RESULT and pin == "KEY1":
        state = STATE_AIM_H
    elif pin == "JOY_PRESS":
        stop()


def game_loop():
    global h_pos, v_pos, p_pos, h_dir, v_dir, p_dir, state, result_text
    last_time = time.time()
    while running:
        now = time.time()
        dt = now - last_time
        last_time = now
        speed = 60  # pixels per second
        if state == STATE_AIM_H:
            h_pos += h_dir * speed * dt / AIM_SLIDER_LENGTH
            if h_pos > 1:
                h_pos = 1
                h_dir = -1
            if h_pos < 0:
                h_pos = 0
                h_dir = 1
        elif state == STATE_AIM_V:
            v_pos += v_dir * speed * dt / AIM_SLIDER_LENGTH
            if v_pos > 1:
                v_pos = 1
                v_dir = -1
            if v_pos < 0:
                v_pos = 0
                v_dir = 1
        elif state == STATE_AIM_P:
            p_pos += p_dir * speed * dt / POWER_SLIDER_LENGTH
            if p_pos > 1:
                p_pos = 1
                p_dir = -1
            if p_pos < 0:
                p_pos = 0
                p_dir = 1
        elif state == STATE_THROW:
            result_text = evaluate_throw()
            time.sleep(0.5)
            state = STATE_RESULT
        draw()
        time.sleep(0.02)


def evaluate_throw():
    h_off = (h_pos - 0.5) * AIM_SLIDER_LENGTH
    v_off = (v_pos - 0.5) * AIM_SLIDER_LENGTH
    power_effect = (0.65 - p_pos) * (TARGET_RADIUS_OUTERMOST * 2)
    target_x = SCREEN_W // 2 + h_off
    # Target is now centered on the screen
    target_y = SCREEN_H // 2 + v_off + power_effect
    # random offset increases with power difference
    acc_mod = 1 - abs(p_pos - 0.65) / 0.65
    acc_mod = max(0, acc_mod)
    max_rand = 10 * (1 - acc_mod ** 2)
    target_x += random.uniform(-max_rand, max_rand)
    target_y += random.uniform(-max_rand, max_rand)
    dx = target_x - SCREEN_W // 2
    dy = target_y - SCREEN_H // 2
    dist = (dx * dx + dy * dy) ** 0.5
    if dist <= TARGET_RADIUS_INNER:
        return "Bullseye! +10"
    if dist <= TARGET_RADIUS_MIDDLE:
        return "Great! +7"
    if dist <= TARGET_RADIUS_OUTER:
        return "On Target +5"
    if dist <= TARGET_RADIUS_OUTERMOST:
        return "Close +3"
    return "Miss"


def draw():
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), "white")
    d = ImageDraw.Draw(img)
    tx = SCREEN_W // 2
    ty = SCREEN_H // 2

    # draw target centered on the screen
    d.ellipse([tx - TARGET_RADIUS_OUTERMOST, ty - TARGET_RADIUS_OUTERMOST,
               tx + TARGET_RADIUS_OUTERMOST, ty + TARGET_RADIUS_OUTERMOST], fill="#d8b373")
    d.ellipse([tx - TARGET_RADIUS_OUTER, ty - TARGET_RADIUS_OUTER,
               tx + TARGET_RADIUS_OUTER, ty + TARGET_RADIUS_OUTER], fill="#c7965c")
    d.ellipse([tx - TARGET_RADIUS_MIDDLE, ty - TARGET_RADIUS_MIDDLE,
               tx + TARGET_RADIUS_MIDDLE, ty + TARGET_RADIUS_MIDDLE], fill="#b07845")
    d.ellipse([tx - TARGET_RADIUS_INNER, ty - TARGET_RADIUS_INNER,
               tx + TARGET_RADIUS_INNER, ty + TARGET_RADIUS_INNER], fill="#e53636")

    # slider/indicator positions
    h_y = ty + TARGET_RADIUS_OUTERMOST + 10
    v_x = tx - TARGET_RADIUS_OUTERMOST - 4
    pow_w = 6
    pow_x0 = v_x - pow_w - 2
    pow_x1 = pow_x0 + pow_w
    pow_top = ty - TARGET_RADIUS_OUTERMOST
    pow_bottom = ty + TARGET_RADIUS_OUTERMOST

    if state == STATE_AIM_H:
        x = tx - AIM_SLIDER_LENGTH // 2 + int(h_pos * AIM_SLIDER_LENGTH)
        d.line([tx - AIM_SLIDER_LENGTH // 2, h_y, tx + AIM_SLIDER_LENGTH // 2, h_y], fill="black")
        d.rectangle([x-2, h_y-4, x+2, h_y+4], fill="blue")
    elif state == STATE_AIM_V:
        y = ty - AIM_SLIDER_LENGTH // 2 + int(v_pos * AIM_SLIDER_LENGTH)
        d.line([v_x, ty - AIM_SLIDER_LENGTH // 2, v_x, ty + AIM_SLIDER_LENGTH // 2], fill="black")
        d.rectangle([v_x-4, y-2, v_x+4, y+2], fill="blue")
        # show locked horizontal slider
        xh = tx - AIM_SLIDER_LENGTH // 2 + int(h_pos * AIM_SLIDER_LENGTH)
        d.line([tx - AIM_SLIDER_LENGTH // 2, h_y, tx + AIM_SLIDER_LENGTH // 2, h_y], fill="gray")
        d.rectangle([xh-2, h_y-4, xh+2, h_y+4], fill="gray")
    elif state == STATE_AIM_P:
        # power meter
        d.rectangle([pow_x0, pow_top, pow_x1, pow_bottom], outline="black")
        fill_height = int(p_pos * (pow_bottom - pow_top))
        d.rectangle([pow_x0+1, pow_bottom-fill_height, pow_x1-1, pow_bottom-1], fill="red")
        # show locked aim sliders
        xh = tx - AIM_SLIDER_LENGTH // 2 + int(h_pos * AIM_SLIDER_LENGTH)
        yv = ty - AIM_SLIDER_LENGTH // 2 + int(v_pos * AIM_SLIDER_LENGTH)
        d.line([tx - AIM_SLIDER_LENGTH // 2, h_y, tx + AIM_SLIDER_LENGTH // 2, h_y], fill="gray")
        d.rectangle([xh-2, h_y-4, xh+2, h_y+4], fill="gray")
        d.line([v_x, ty - AIM_SLIDER_LENGTH // 2, v_x, ty + AIM_SLIDER_LENGTH // 2], fill="gray")
        d.rectangle([v_x-4, yv-2, v_x+4, yv+2], fill="gray")
    elif state == STATE_RESULT:
        d.text((10, SCREEN_H - 30), result_text, font=fonts[0], fill="black")
        xh = tx - AIM_SLIDER_LENGTH // 2 + int(h_pos * AIM_SLIDER_LENGTH)
        yv = ty - AIM_SLIDER_LENGTH // 2 + int(v_pos * AIM_SLIDER_LENGTH)
        d.line([tx - AIM_SLIDER_LENGTH // 2, h_y, tx + AIM_SLIDER_LENGTH // 2, h_y], fill="gray")
        d.rectangle([xh-2, h_y-4, xh+2, h_y+4], fill="gray")
        d.line([v_x, ty - AIM_SLIDER_LENGTH // 2, v_x, ty + AIM_SLIDER_LENGTH // 2], fill="gray")
        d.rectangle([v_x-4, yv-2, v_x+4, yv+2], fill="gray")
        d.rectangle([pow_x0, pow_top, pow_x1, pow_bottom], outline="black")
        fill_height = int(p_pos * (pow_bottom - pow_top))
        d.rectangle([pow_x0+1, pow_bottom-fill_height, pow_x1-1, pow_bottom-1], fill="gray")
    thread_safe_display(img)
