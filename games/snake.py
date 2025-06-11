import random
import threading
import time
from collections import deque
from PIL import Image, ImageDraw

CELL_SIZE = 8
GRID_WIDTH = 128 // CELL_SIZE
GRID_HEIGHT = 128 // CELL_SIZE

thread_safe_display = None
fonts = None
exit_cb = None

snake = deque()
direction = (1, 0)
food = (0, 0)
running = False
update_thread = None


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    """Start the Snake game."""
    global running, snake, direction, food, update_thread
    running = True
    snake = deque([(GRID_WIDTH // 2, GRID_HEIGHT // 2)])
    direction = (1, 0)
    place_food()
    update_thread = threading.Thread(target=game_loop, daemon=True)
    update_thread.start()
    draw()


def handle_input(pin):
    """Handle joystick/button input."""
    global direction, running
    if not running:
        return
    if pin == "JOY_UP" and direction != (0, 1):
        direction = (0, -1)
    elif pin == "JOY_DOWN" and direction != (0, -1):
        direction = (0, 1)
    elif pin == "JOY_LEFT" and direction != (1, 0):
        direction = (-1, 0)
    elif pin == "JOY_RIGHT" and direction != (-1, 0):
        direction = (1, 0)
    elif pin == "KEY1":
        stop()


def game_loop():
    global running, snake
    while running:
        time.sleep(0.3)
        head = (snake[0][0] + direction[0], snake[0][1] + direction[1])
        if (
            head in snake
            or head[0] < 0
            or head[0] >= GRID_WIDTH
            or head[1] < 0
            or head[1] >= GRID_HEIGHT
        ):
            running = False
            draw_game_over()
            time.sleep(2)
            exit_cb()
            return
        snake.appendleft(head)
        if head == food:
            place_food()
        else:
            snake.pop()
        draw()


def draw():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    for x, y in snake:
        d.rectangle(
            [x * CELL_SIZE, y * CELL_SIZE, x * CELL_SIZE + CELL_SIZE - 1, y * CELL_SIZE + CELL_SIZE - 1],
            fill=(0, 255, 0),
        )
    fx, fy = food
    d.rectangle(
        [fx * CELL_SIZE, fy * CELL_SIZE, fx * CELL_SIZE + CELL_SIZE - 1, fy * CELL_SIZE + CELL_SIZE - 1],
        fill=(255, 0, 0),
    )
    thread_safe_display(img)


def draw_game_over():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    font = fonts[1]
    d.text((20, 50), "Game Over", font=font, fill=(255, 0, 0))
    thread_safe_display(img)


def place_food():
    global food
    while True:
        f = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
        if f not in snake:
            food = f
            break


def stop():
    global running
    running = False
    if update_thread:
        update_thread.join()
    exit_cb()
