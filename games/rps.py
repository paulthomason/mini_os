import random
import time
from PIL import Image, ImageDraw

thread_safe_display = None
fonts = None
exit_cb = None

CHOICES = ["Rock", "Paper", "Scissors"]


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    draw_prompt()


def handle_input(pin):
    if pin == "KEY1":
        play(0)
    elif pin == "KEY2":
        play(1)
    elif pin == "KEY3":
        play(2)
    elif pin == "JOY_PRESS":
        exit_cb()


def play(choice):
    cpu = random.randint(0, 2)
    result = determine(choice, cpu)
    draw_result(choice, cpu, result)
    time.sleep(2)
    exit_cb()


def determine(user, cpu):
    if user == cpu:
        return "Tie"
    if (user == 0 and cpu == 2) or (user == 1 and cpu == 0) or (user == 2 and cpu == 1):
        return "You Win"
    return "You Lose"


def draw_prompt():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    d.text((5, 5), "1=Rock 2=Paper 3=Scissors", font=fonts[0], fill=(0, 255, 255))
    d.text((25, 60), "Make Choice", font=fonts[1], fill=(255, 255, 255))
    thread_safe_display(img)


def draw_result(user, cpu, result):
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    d.text((5, 5), f"You: {CHOICES[user]}", font=fonts[0], fill=(255, 255, 0))
    d.text((5, 20), f"CPU: {CHOICES[cpu]}", font=fonts[0], fill=(255, 255, 0))
    d.text((30, 60), result, font=fonts[1], fill=(255, 0, 0))
    thread_safe_display(img)
