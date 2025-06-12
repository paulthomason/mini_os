# Simple pico-8 style RPG inspired by World of Warcraft
# Players move around a small grid and defeat roaming enemies.

import threading
import time
import random
from PIL import Image, ImageDraw

# Constants
TILE_SIZE = 8
GRID_W = 16
GRID_H = 16
SCREEN_W = GRID_W * TILE_SIZE
SCREEN_H = GRID_H * TILE_SIZE
MAX_HP = 10
LEVEL_THRESH = 5
HEART_HEAL = 3

thread_safe_display = None
fonts = None
exit_cb = None

running = False
update_thread = None

# Game state
player_pos = [GRID_W // 2, GRID_H // 2]
player_hp = MAX_HP
score = 0
level = 1
heart_pos = None

class Enemy:
    def __init__(self):
        self.x = random.randint(0, GRID_W - 1)
        self.y = random.randint(0, GRID_H - 1)
        self.hp = random.randint(1, 3)
        self.speed = random.choice([1, 1, 2])

enemies = []


def init(display_func, fonts_tuple, quit_callback):
    """Initialize module level references."""
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    """Start the game."""
    global running, update_thread, player_pos, player_hp, score, enemies, level, heart_pos
    player_pos = [GRID_W // 2, GRID_H // 2]
    player_hp = MAX_HP
    score = 0
    level = 1
    heart_pos = None
    enemies = [Enemy() for _ in range(3)]
    running = True
    update_thread = threading.Thread(target=_game_loop, daemon=True)
    update_thread.start()
    draw()


def stop():
    """Stop the game and return to the menu."""
    global running
    running = False
    if update_thread:
        update_thread.join()
    exit_cb()


def handle_input(pin):
    """Process joystick and button input."""
    if pin == "KEY2":
        stop()
        return

    if pin == "JOY_UP":
        _move_player(0, -1)
    elif pin == "JOY_DOWN":
        _move_player(0, 1)
    elif pin == "JOY_LEFT":
        _move_player(-1, 0)
    elif pin == "JOY_RIGHT":
        _move_player(1, 0)
    elif pin in ("JOY_PRESS", "KEY1"):
        _attack()
    draw()


def _move_player(dx, dy):
    if not running:
        return
    nx = max(0, min(GRID_W - 1, player_pos[0] + dx))
    ny = max(0, min(GRID_H - 1, player_pos[1] + dy))
    player_pos[0], player_pos[1] = nx, ny
    _check_heart()


def _attack():
    global score, enemies, level
    for enemy in enemies:
        if abs(enemy.x - player_pos[0]) + abs(enemy.y - player_pos[1]) == 1:
            enemy.hp -= 1
            if enemy.hp <= 0:
                score += 1
                enemies.remove(enemy)
                enemies.append(Enemy())
                if score % LEVEL_THRESH == 0:
                    level += 1
                    enemies.append(Enemy())
                    _maybe_spawn_heart(force=True)
            break


def _game_loop():
    global player_hp, running
    while running and player_hp > 0:
        for enemy in list(enemies):
            for _ in range(enemy.speed):
                _move_enemy(enemy)
            if enemy.x == player_pos[0] and enemy.y == player_pos[1]:
                player_hp -= 1
                if player_hp <= 0:
                    break
        _maybe_spawn_heart()
        draw()
        delay = max(0.5 - (level - 1) * 0.05, 0.2)
        time.sleep(delay)
    running = False
    draw_game_over()
    time.sleep(2)
    exit_cb()


def _move_enemy(enemy):
    if random.random() < 0.5:
        dx = 1 if enemy.x < player_pos[0] else -1 if enemy.x > player_pos[0] else 0
        dy = 1 if enemy.y < player_pos[1] else -1 if enemy.y > player_pos[1] else 0
        if dx and dy:
            if random.random() < 0.5:
                dx = 0
            else:
                dy = 0
    else:
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)]
        dx, dy = random.choice(dirs)
    enemy.x = max(0, min(GRID_W - 1, enemy.x + dx))
    enemy.y = max(0, min(GRID_H - 1, enemy.y + dy))


def _maybe_spawn_heart(force=False):
    """Occasionally spawn a heart power-up."""
    global heart_pos
    if heart_pos is None and (force or random.random() < 0.1):
        while True:
            pos = (random.randint(0, GRID_W - 1), random.randint(0, GRID_H - 1))
            if pos != tuple(player_pos) and all((e.x, e.y) != pos for e in enemies):
                heart_pos = pos
                break


def _check_heart():
    """Collect heart if player steps on it."""
    global heart_pos, player_hp
    if heart_pos and tuple(player_pos) == heart_pos:
        player_hp = min(MAX_HP, player_hp + HEART_HEAL)
        heart_pos = None


def draw():
    """Render the current game state."""
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), "black")
    d = ImageDraw.Draw(img)

    # Draw grid
    for x in range(GRID_W):
        for y in range(GRID_H):
            rect = [x * TILE_SIZE, y * TILE_SIZE, (x + 1) * TILE_SIZE - 1, (y + 1) * TILE_SIZE - 1]
            d.rectangle(rect, outline=(40, 40, 40))

    # Draw enemies
    for enemy in enemies:
        rect = [enemy.x * TILE_SIZE, enemy.y * TILE_SIZE, (enemy.x + 1) * TILE_SIZE - 1, (enemy.y + 1) * TILE_SIZE - 1]
        d.rectangle(rect, fill=(255, 0, 0))

    # Draw heart
    if heart_pos:
        hx, hy = heart_pos
        rect = [hx * TILE_SIZE, hy * TILE_SIZE, (hx + 1) * TILE_SIZE - 1, (hy + 1) * TILE_SIZE - 1]
        d.rectangle(rect, fill=(255, 0, 255))

    # Draw player
    px, py = player_pos
    rect = [px * TILE_SIZE, py * TILE_SIZE, (px + 1) * TILE_SIZE - 1, (py + 1) * TILE_SIZE - 1]
    d.rectangle(rect, fill=(0, 0, 255))

    # HUD
    d.text((2, 2), f"HP:{player_hp} Score:{score} Lv:{level}", font=fonts[0], fill=(255, 255, 0))

    thread_safe_display(img)


def draw_game_over():
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), "black")
    d = ImageDraw.Draw(img)
    d.text((20, 50), "Game Over", font=fonts[1], fill=(255, 0, 0))
    d.text((20, 70), f"Score: {score}", font=fonts[1], fill=(255, 255, 0))
    thread_safe_display(img)

