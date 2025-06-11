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

# Slider speed settings
BASE_SPEED = 60
SPEED_MULTIPLIER = 1.4
current_speed = BASE_SPEED

# Axe landing position
axe_x = SCREEN_W // 2
axe_y = SCREEN_H

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
score = 0


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global running, state, h_pos, v_pos, p_pos, h_dir, v_dir, p_dir, current_speed, score
    running = True
    state = STATE_AIM_H
    h_pos = v_pos = p_pos = 0.0
    h_dir = v_dir = p_dir = 1
    current_speed = BASE_SPEED
    score = 0
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
    global state, h_dir, v_dir, p_dir, result_text, current_speed
    if pin == "KEY2":
        stop()
        return
    if state in (STATE_AIM_H, STATE_AIM_V, STATE_AIM_P) and pin == "KEY1":
        if state == STATE_AIM_H:
            state = STATE_AIM_V
            current_speed *= SPEED_MULTIPLIER
        elif state == STATE_AIM_V:
            state = STATE_AIM_P
            current_speed *= SPEED_MULTIPLIER
        else:
            state = STATE_THROW
    elif state == STATE_RESULT and pin == "KEY1":
        state = STATE_AIM_H
        current_speed = BASE_SPEED
    elif pin == "JOY_PRESS":
        stop()


def game_loop():
    global h_pos, v_pos, p_pos, h_dir, v_dir, p_dir, state, result_text, axe_x, axe_y, current_speed, score
    last_time = time.time()
    while running:
        now = time.time()
        dt = now - last_time
        last_time = now
        speed = current_speed  # pixels per second
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
            result_text, points, axe_x, axe_y = evaluate_throw()
            score += points
            animate_throw(axe_x, axe_y)
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
        text = "Bullseye! +10"
        points = 10
    elif dist <= TARGET_RADIUS_MIDDLE:
        text = "Great! +7"
        points = 7
    elif dist <= TARGET_RADIUS_OUTER:
        text = "On Target +5"
        points = 5
    elif dist <= TARGET_RADIUS_OUTERMOST:
        text = "Close +3"
        points = 3
    else:
        text = "Miss"
        points = 0
    return text, points, int(target_x), int(target_y)


def animate_throw(tx, ty):
    global axe_x, axe_y
    start_x = SCREEN_W // 2
    start_y = SCREEN_H
    steps = 10
    for i in range(steps + 1):
        axe_x = int(start_x + (tx - start_x) * i / steps)
        axe_y = int(start_y + (ty - start_y) * i / steps)
        draw()
        time.sleep(0.05)


def draw_axe(d, x, y):
    """Draw a simple axe shape centered at (x, y)."""
    d.rectangle([x - 1, y - 6, x + 1, y + 6], fill="#8B4513")
    d.polygon([(x - 2, y - 6), (x + 6, y - 2), (x + 6, y + 2), (x - 2, y + 6)], fill="gray")


def draw():
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), "white")
    d = ImageDraw.Draw(img)
    d.text((5, 5), f"Score: {score}", font=fonts[0], fill="black")
    tx = SCREEN_W // 2
    ty = SCREEN_H // 2

    # draw target centered on the screen with brighter colors
    d.ellipse([tx - TARGET_RADIUS_OUTERMOST, ty - TARGET_RADIUS_OUTERMOST,
               tx + TARGET_RADIUS_OUTERMOST, ty + TARGET_RADIUS_OUTERMOST], fill="#2196f3")
    d.ellipse([tx - TARGET_RADIUS_OUTER, ty - TARGET_RADIUS_OUTER,
               tx + TARGET_RADIUS_OUTER, ty + TARGET_RADIUS_OUTER], fill="#4caf50")
    d.ellipse([tx - TARGET_RADIUS_MIDDLE, ty - TARGET_RADIUS_MIDDLE,
               tx + TARGET_RADIUS_MIDDLE, ty + TARGET_RADIUS_MIDDLE], fill="#ffeb3b")
    d.ellipse([tx - TARGET_RADIUS_INNER, ty - TARGET_RADIUS_INNER,
               tx + TARGET_RADIUS_INNER, ty + TARGET_RADIUS_INNER], fill="#f44336")

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
    elif state == STATE_THROW:
        xh = tx - AIM_SLIDER_LENGTH // 2 + int(h_pos * AIM_SLIDER_LENGTH)
        yv = ty - AIM_SLIDER_LENGTH // 2 + int(v_pos * AIM_SLIDER_LENGTH)
        d.line([tx - AIM_SLIDER_LENGTH // 2, h_y, tx + AIM_SLIDER_LENGTH // 2, h_y], fill="gray")
        d.rectangle([xh-2, h_y-4, xh+2, h_y+4], fill="gray")
        d.line([v_x, ty - AIM_SLIDER_LENGTH // 2, v_x, ty + AIM_SLIDER_LENGTH // 2], fill="gray")
        d.rectangle([v_x-4, yv-2, v_x+4, yv+2], fill="gray")
        d.rectangle([pow_x0, pow_top, pow_x1, pow_bottom], outline="black")
        fill_height = int(p_pos * (pow_bottom - pow_top))
        d.rectangle([pow_x0+1, pow_bottom-fill_height, pow_x1-1, pow_bottom-1], fill="gray")
        draw_axe(d, axe_x, axe_y)
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
        draw_axe(d, axe_x, axe_y)
    thread_safe_display(img)
