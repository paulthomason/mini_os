import threading
import time
import random
from PIL import Image, ImageDraw

SCREEN_W = 128
SCREEN_H = 128

# Target radii based on canvas size
BASE = min(SCREEN_W, SCREEN_H)
TARGET_RADIUS_OUTERMOST = int(BASE * 0.225)
TARGET_RADIUS_OUTER = int(BASE * 0.167)
TARGET_RADIUS_MIDDLE = int(BASE * 0.108)
TARGET_RADIUS_INNER = int(BASE * 0.05)
AIM_SLIDER_LENGTH = int(TARGET_RADIUS_OUTERMOST * 2 * 1.3)
POWER_SLIDER_LENGTH = int(TARGET_RADIUS_OUTERMOST * 2)

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
    target_y = SCREEN_H // 3 + v_off + power_effect
    # random offset increases with power difference
    acc_mod = 1 - abs(p_pos - 0.65) / 0.65
    acc_mod = max(0, acc_mod)
    max_rand = 10 * (1 - acc_mod ** 2)
    target_x += random.uniform(-max_rand, max_rand)
    target_y += random.uniform(-max_rand, max_rand)
    dx = target_x - SCREEN_W // 2
    dy = target_y - SCREEN_H // 3
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
    ty = SCREEN_H // 3
    # target
    d.ellipse([tx - TARGET_RADIUS_OUTERMOST, ty - TARGET_RADIUS_OUTERMOST,
               tx + TARGET_RADIUS_OUTERMOST, ty + TARGET_RADIUS_OUTERMOST], fill="#d8b373")
    d.ellipse([tx - TARGET_RADIUS_OUTER, ty - TARGET_RADIUS_OUTER,
               tx + TARGET_RADIUS_OUTER, ty + TARGET_RADIUS_OUTER], fill="#c7965c")
    d.ellipse([tx - TARGET_RADIUS_MIDDLE, ty - TARGET_RADIUS_MIDDLE,
               tx + TARGET_RADIUS_MIDDLE, ty + TARGET_RADIUS_MIDDLE], fill="#b07845")
    d.ellipse([tx - TARGET_RADIUS_INNER, ty - TARGET_RADIUS_INNER,
               tx + TARGET_RADIUS_INNER, ty + TARGET_RADIUS_INNER], fill="#e53636")

    if state == STATE_AIM_H:
        x = tx - AIM_SLIDER_LENGTH//2 + int(h_pos*AIM_SLIDER_LENGTH)
        d.line([x, ty - TARGET_RADIUS_OUTERMOST - 15, x, ty + TARGET_RADIUS_OUTERMOST + 15], fill="blue")
    elif state == STATE_AIM_V:
        y = ty - AIM_SLIDER_LENGTH//2 + int(v_pos*AIM_SLIDER_LENGTH)
        d.line([tx - TARGET_RADIUS_OUTERMOST - 15, y, tx + TARGET_RADIUS_OUTERMOST + 15, y], fill="blue")
        x = tx - AIM_SLIDER_LENGTH//2 + int(h_pos*AIM_SLIDER_LENGTH)
        d.line([x, ty - TARGET_RADIUS_OUTERMOST - 15, x, ty + TARGET_RADIUS_OUTERMOST + 15], fill="gray")
    elif state == STATE_AIM_P:
        y = SCREEN_H - 20
        x0 = tx - POWER_SLIDER_LENGTH//2
        x1 = tx + POWER_SLIDER_LENGTH//2
        d.line([x0, y, x1, y], fill="black")
        x = x0 + int(p_pos*POWER_SLIDER_LENGTH)
        d.rectangle([x-2, y-8, x+2, y+8], fill="red")
        # draw previous sliders locked
        xh = tx - AIM_SLIDER_LENGTH//2 + int(h_pos*AIM_SLIDER_LENGTH)
        d.line([xh, ty - TARGET_RADIUS_OUTERMOST - 15, xh, ty + TARGET_RADIUS_OUTERMOST + 15], fill="gray")
        yv = ty - AIM_SLIDER_LENGTH//2 + int(v_pos*AIM_SLIDER_LENGTH)
        d.line([tx - TARGET_RADIUS_OUTERMOST - 15, yv, tx + TARGET_RADIUS_OUTERMOST + 15, yv], fill="gray")
    elif state == STATE_RESULT:
        d.text((10, SCREEN_H - 30), result_text, font=fonts[0], fill="black")
        # show locked sliders
        xh = tx - AIM_SLIDER_LENGTH//2 + int(h_pos*AIM_SLIDER_LENGTH)
        d.line([xh, ty - TARGET_RADIUS_OUTERMOST - 15, xh, ty + TARGET_RADIUS_OUTERMOST + 15], fill="gray")
        yv = ty - AIM_SLIDER_LENGTH//2 + int(v_pos*AIM_SLIDER_LENGTH)
        d.line([tx - TARGET_RADIUS_OUTERMOST - 15, yv, tx + TARGET_RADIUS_OUTERMOST + 15, yv], fill="gray")
        # power slider
        y = SCREEN_H - 20
        x0 = tx - POWER_SLIDER_LENGTH//2
        x = x0 + int(p_pos*POWER_SLIDER_LENGTH)
        d.rectangle([x-2, y-8, x+2, y+8], fill="gray")
    thread_safe_display(img)
