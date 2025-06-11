import random
import threading
import time
from PIL import Image, ImageDraw

CELL_SIZE = 8
BOARD_W = 10
BOARD_H = 16

thread_safe_display = None
fonts = None
exit_cb = None

board = []
current = None
rotation = 0
piece_x = 0
piece_y = 0
running = False
update_thread = None

# Tetromino shapes using coordinates for each rotation
TETROMINOES = {
    "I": [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
    ],
    "O": [[(1, 0), (2, 0), (1, 1), (2, 1)]],
    "T": [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)],
    ],
    "L": [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)],
    ],
    "J": [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
    ],
    "S": [
        [(1, 0), (2, 0), (0, 1), (1, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)],
    ],
    "Z": [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(2, 0), (1, 1), (2, 1), (1, 2)],
    ],
}


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global board, running
    board = [[0 for _ in range(BOARD_W)] for _ in range(BOARD_H)]
    running = True
    spawn_piece()
    draw()
    start_thread()


def start_thread():
    global update_thread
    update_thread = threading.Thread(target=game_loop, daemon=True)
    update_thread.start()


def spawn_piece():
    global current, rotation, piece_x, piece_y
    current = random.choice(list(TETROMINOES.values()))
    rotation = 0
    piece_x = BOARD_W // 2 - 2
    piece_y = 0
    if collision(piece_x, piece_y, rotation):
        game_over()


def rotate_piece():
    global rotation
    new_rot = (rotation + 1) % len(current)
    if not collision(piece_x, piece_y, new_rot):
        rotation = new_rot


def move(dx, dy):
    global piece_x, piece_y
    if not collision(piece_x + dx, piece_y + dy, rotation):
        piece_x += dx
        piece_y += dy
        return True
    return False


def drop():
    while move(0, 1):
        pass
    lock_piece()


def collision(x, y, rot):
    for px, py in current[rot]:
        nx = x + px
        ny = y + py
        if nx < 0 or nx >= BOARD_W or ny >= BOARD_H:
            return True
        if ny >= 0 and board[ny][nx]:
            return True
    return False


def lock_piece():
    for px, py in current[rotation]:
        nx = piece_x + px
        ny = piece_y + py
        if 0 <= ny < BOARD_H:
            board[ny][nx] = 1
    clear_rows()
    spawn_piece()


def clear_rows():
    global board
    board = [row for row in board if not all(row)]
    while len(board) < BOARD_H:
        board.insert(0, [0 for _ in range(BOARD_W)])


def game_loop():
    while running:
        time.sleep(0.5)
        if not move(0, 1):
            lock_piece()
        draw()


def game_over():
    global running
    running = False
    draw_game_over()
    time.sleep(2)
    exit_cb()


def handle_input(pin):
    if pin == "JOY_LEFT":
        move(-1, 0)
    elif pin == "JOY_RIGHT":
        move(1, 0)
    elif pin == "JOY_DOWN":
        if not move(0, 1):
            lock_piece()
    elif pin == "JOY_PRESS" or pin == "KEY3":
        drop()
    elif pin == "KEY1":
        rotate_piece()
    elif pin == "KEY2":
        stop()
    draw()


def stop():
    global running
    running = False
    if update_thread:
        update_thread.join()
    exit_cb()


def draw():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    off_x = (128 - BOARD_W * CELL_SIZE) // 2
    off_y = 0
    # Draw settled blocks
    for y in range(BOARD_H):
        for x in range(BOARD_W):
            if board[y][x]:
                d.rectangle(
                    [
                        off_x + x * CELL_SIZE,
                        off_y + y * CELL_SIZE,
                        off_x + x * CELL_SIZE + CELL_SIZE - 1,
                        off_y + y * CELL_SIZE + CELL_SIZE - 1,
                    ],
                    fill=(0, 255, 255),
                )
    # Draw current piece
    for px, py in current[rotation]:
        nx = piece_x + px
        ny = piece_y + py
        d.rectangle(
            [
                off_x + nx * CELL_SIZE,
                off_y + ny * CELL_SIZE,
                off_x + nx * CELL_SIZE + CELL_SIZE - 1,
                off_y + ny * CELL_SIZE + CELL_SIZE - 1,
            ],
            fill=(255, 0, 0),
        )
    thread_safe_display(img)


def draw_game_over():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    d.text((20, 50), "Game Over", font=fonts[1], fill=(255, 0, 0))
    thread_safe_display(img)
