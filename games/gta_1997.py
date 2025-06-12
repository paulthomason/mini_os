import random
import threading
import time
from PIL import Image, ImageDraw

CELL_SIZE = 8
GRID_W = 16
GRID_H = 16

thread_safe_display = None
fonts = None
exit_cb = None

map_grid = []
player = [7, 7]
star = (0, 0)
enemies = []
score = 0
lives = 3
running = False
update_thread = None
start_time = 0
GAME_TIME = 30  # seconds


def spawn_enemies():
    """Create enemy cars that patrol the roads."""
    global enemies
    enemies = [
        [0, 7, 1, 0],
        [GRID_W - 1, 8, -1, 0],
        [7, 0, 0, 1],
        [8, GRID_H - 1, 0, -1],
    ]

def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback

def start():
    global map_grid, player, star, enemies, score, lives, running, update_thread, start_time
    map_grid = [[1 for _ in range(GRID_W)] for _ in range(GRID_H)]
    for y in range(1, GRID_H - 1):
        map_grid[y][7] = 0
        map_grid[y][8] = 0
    for x in range(1, GRID_W - 1):
        map_grid[7][x] = 0
        map_grid[8][x] = 0
    player = [7, 7]
    score = 0
    lives = 3
    spawn_enemies()
    place_star()
    running = True
    start_time = time.time()
    update_thread = threading.Thread(target=game_loop, daemon=True)
    update_thread.start()
    draw()

def handle_input(pin):
    global player, running
    if not running:
        return
    dx = dy = 0
    if pin == "JOY_UP":
        dy = -1
    elif pin == "JOY_DOWN":
        dy = 1
    elif pin == "JOY_LEFT":
        dx = -1
    elif pin == "JOY_RIGHT":
        dx = 1
    elif pin in ("KEY2", "JOY_PRESS"):
        stop()
        return
    nx = player[0] + dx
    ny = player[1] + dy
    if 0 <= nx < GRID_W and 0 <= ny < GRID_H and map_grid[ny][nx] == 0:
        player[0] = nx
        player[1] = ny
    check_player_collisions()
    draw()

def game_loop():
    global running
    while running:
        if time.time() - start_time >= GAME_TIME:
            running = False
            draw_game_over()
            time.sleep(2)
            exit_cb()
            return
        move_enemies()
        check_player_collisions()
        if tuple(player) == star:
            increase_score()
        time.sleep(0.1)
        draw()

def place_star():
    global star
    while True:
        sx = random.randint(1, GRID_W - 2)
        sy = random.randint(1, GRID_H - 2)
        if map_grid[sy][sx] == 0 and [sx, sy] != player and all([
            sx != e[0] or sy != e[1] for e in enemies
        ]):
            star = (sx, sy)
            break

def increase_score():
    global score
    score += 1
    place_star()


def move_enemies():
    """Advance enemy cars along their paths."""
    for e in enemies:
        e[0] = (e[0] + e[2]) % GRID_W
        e[1] = (e[1] + e[3]) % GRID_H


def check_player_collisions():
    """Handle collisions between the player and enemies or pickups."""
    global lives, running
    for e in enemies:
        if player[0] == e[0] and player[1] == e[1]:
            lives -= 1
            player[0], player[1] = 7, 7
            if lives <= 0:
                running = False
                draw_game_over()
                time.sleep(2)
                exit_cb()
            return

def stop():
    global running
    running = False
    if update_thread:
        update_thread.join()
    exit_cb()

def draw():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    for y in range(GRID_H):
        for x in range(GRID_W):
            if map_grid[y][x] == 1:
                d.rectangle(
                    [x * CELL_SIZE, y * CELL_SIZE, x * CELL_SIZE + CELL_SIZE - 1, y * CELL_SIZE + CELL_SIZE - 1],
                    fill=(60, 60, 60),
                )
    sx, sy = star
    d.rectangle(
        [sx * CELL_SIZE, sy * CELL_SIZE, sx * CELL_SIZE + CELL_SIZE - 1, sy * CELL_SIZE + CELL_SIZE - 1],
        fill=(255, 255, 0),
    )
    px, py = player
    d.rectangle(
        [px * CELL_SIZE, py * CELL_SIZE, px * CELL_SIZE + CELL_SIZE - 1, py * CELL_SIZE + CELL_SIZE - 1],
        fill=(0, 0, 255),
    )
    for ex, ey, _, _ in enemies:
        d.rectangle(
            [ex * CELL_SIZE, ey * CELL_SIZE, ex * CELL_SIZE + CELL_SIZE - 1, ey * CELL_SIZE + CELL_SIZE - 1],
            fill=(255, 0, 0),
        )
    d.text((2, 2), f"Score: {score}", font=fonts[0], fill=(255, 255, 255))
    remaining = max(0, int(GAME_TIME - (time.time() - start_time)))
    d.text((80, 2), f"{remaining}s", font=fonts[0], fill=(255, 255, 255))
    d.text((2, 118), f"Lives: {lives}", font=fonts[0], fill=(255, 255, 255))
    thread_safe_display(img)

def draw_game_over():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    msg = "Time Up" if lives > 0 else "Game Over"
    d.text((30, 50), msg, font=fonts[1], fill=(255, 0, 0))
    d.text((30, 70), f"Score: {score}", font=fonts[1], fill=(0, 255, 255))
    thread_safe_display(img)
