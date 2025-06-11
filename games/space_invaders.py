import threading
import time
from PIL import Image, ImageDraw

CELL_SIZE = 8
INV_COLS = 8
INV_ROWS = 3
SCREEN_W = 128
SCREEN_H = 128

thread_safe_display = None
fonts = None
exit_cb = None

ship_x = SCREEN_W // 2
invaders = []
bullet = None
move_dir = 1
running = False
update_thread = None


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global invaders, ship_x, bullet, move_dir, running
    ship_x = SCREEN_W // 2
    bullet = None
    move_dir = 1
    invaders = [(x * 12 + 16, y * 10 + 10) for y in range(INV_ROWS) for x in range(INV_COLS)]
    running = True
    draw()
    start_thread()


def start_thread():
    global update_thread
    update_thread = threading.Thread(target=game_loop, daemon=True)
    update_thread.start()


def handle_input(pin):
    global ship_x, bullet
    if pin == "JOY_LEFT":
        ship_x = max(0, ship_x - 8)
    elif pin == "JOY_RIGHT":
        ship_x = min(SCREEN_W - CELL_SIZE, ship_x + 8)
    elif pin in ("JOY_PRESS", "KEY1"):
        if bullet is None:
            bullet = [ship_x + CELL_SIZE // 2, SCREEN_H - 12]
    elif pin == "KEY2":
        stop()
    draw()


def game_loop():
    global bullet, invaders, move_dir, running
    while running:
        time.sleep(0.2)
        # move bullet
        if bullet is not None:
            bullet[1] -= 8
            if bullet[1] < 0:
                bullet = None
            else:
                hit = None
                for inv in invaders:
                    if abs(bullet[0] - inv[0]) < CELL_SIZE and abs(bullet[1] - inv[1]) < CELL_SIZE:
                        hit = inv
                        break
                if hit:
                    invaders.remove(hit)
                    bullet = None
        # move invaders
        edge_hit = False
        for i, inv in enumerate(invaders):
            invaders[i] = (inv[0] + move_dir * 4, inv[1])
            if invaders[i][0] <= 0 or invaders[i][0] >= SCREEN_W - CELL_SIZE:
                edge_hit = True
        if edge_hit:
            move_dir *= -1
            invaders = [(x, y + 4) for (x, y) in invaders]
        if any(y >= SCREEN_H - 20 for x, y in invaders):
            running = False
            draw_game_over()
            time.sleep(2)
            exit_cb()
            return
        if not invaders:
            running = False
            draw_victory()
            time.sleep(2)
            exit_cb()
            return
        draw()


def stop():
    global running
    running = False
    if update_thread:
        update_thread.join()
    exit_cb()


def draw():
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), "black")
    d = ImageDraw.Draw(img)
    # draw ship
    d.rectangle([ship_x, SCREEN_H - 8, ship_x + CELL_SIZE, SCREEN_H], fill=(0, 255, 0))
    # draw invaders
    for x, y in invaders:
        d.rectangle([x, y, x + CELL_SIZE, y + CELL_SIZE], fill=(255, 0, 0))
    if bullet is not None:
        d.rectangle([bullet[0] - 1, bullet[1], bullet[0] + 1, bullet[1] + 4], fill=(255, 255, 255))
    thread_safe_display(img)


def draw_game_over():
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), "black")
    d = ImageDraw.Draw(img)
    d.text((20, 50), "Game Over", font=fonts[1], fill=(255, 0, 0))
    thread_safe_display(img)


def draw_victory():
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), "black")
    d = ImageDraw.Draw(img)
    d.text((30, 50), "You Win", font=fonts[1], fill=(0, 255, 0))
    thread_safe_display(img)
