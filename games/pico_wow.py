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

thread_safe_display = None
fonts = None
exit_cb = None

running = False
update_thread = None

# Game state
player_pos = [GRID_W // 2, GRID_H // 2]
player_hp = 10
score = 0

class Enemy:
    def __init__(self):
        self.x = random.randint(0, GRID_W - 1)
        self.y = random.randint(0, GRID_H - 1)
        self.hp = random.randint(1, 3)

enemies = []


def init(display_func, fonts_tuple, quit_callback):
    """Initialize module level references."""
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    """Start the game."""
    global running, update_thread, player_pos, player_hp, score, enemies
    player_pos = [GRID_W // 2, GRID_H // 2]
    player_hp = 10
    score = 0
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


def _attack():
    global score, enemies
    for enemy in enemies:
        if abs(enemy.x - player_pos[0]) + abs(enemy.y - player_pos[1]) == 1:
            enemy.hp -= 1
            if enemy.hp <= 0:
                score += 1
                enemies.remove(enemy)
                enemies.append(Enemy())
            break


def _game_loop():
    global player_hp, running
    while running and player_hp > 0:
        for enemy in list(enemies):
            _move_enemy(enemy)
            if enemy.x == player_pos[0] and enemy.y == player_pos[1]:
                player_hp -= 1
                if player_hp <= 0:
                    break
        draw()
        time.sleep(0.5)
    running = False
    draw_game_over()
    time.sleep(2)
    exit_cb()


def _move_enemy(enemy):
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)]
    dx, dy = random.choice(dirs)
    enemy.x = max(0, min(GRID_W - 1, enemy.x + dx))
    enemy.y = max(0, min(GRID_H - 1, enemy.y + dy))


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

    # Draw player
    px, py = player_pos
    rect = [px * TILE_SIZE, py * TILE_SIZE, (px + 1) * TILE_SIZE - 1, (py + 1) * TILE_SIZE - 1]
    d.rectangle(rect, fill=(0, 0, 255))

    # HUD
    d.text((2, 2), f"HP:{player_hp} Score:{score}", font=fonts[0], fill=(255, 255, 0))

    thread_safe_display(img)


def draw_game_over():
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), "black")
    d = ImageDraw.Draw(img)
    d.text((20, 50), "Game Over", font=fonts[1], fill=(255, 0, 0))
    d.text((20, 70), f"Score: {score}", font=fonts[1], fill=(255, 255, 0))
    thread_safe_display(img)

