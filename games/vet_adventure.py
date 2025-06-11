import time
from PIL import Image, ImageDraw

thread_safe_display = None
fonts = None
exit_cb = None

state = "start"

STEPS = {
    "start": {
        "text": ["Gorgina sits at", "the referral desk."],
        "choices": [
            ("Answer phone", "phone"),
            ("Check schedule", "schedule"),
            ("Go home", "end"),
        ],
    },
    "phone": {
        "text": ["A vet requests", "an ortho consult."],
        "choices": [
            ("Book it", "booked"),
            ("Ask for email", "email"),
            ("Hang up", "end"),
        ],
    },
    "schedule": {
        "text": ["A slot opens at", "3pm this afternoon."],
        "choices": [
            ("Call to confirm", "booked"),
            ("Leave open", "end"),
            ("Back", "start"),
        ],
    },
    "email": {
        "text": ["They'll send", "records later."],
        "choices": [
            ("Back to desk", "start"),
        ],
    },
    "booked": {
        "text": ["Consult scheduled!", "Great job Gorgina!"],
        "choices": [
            ("Another call", "phone"),
            ("End day", "end"),
        ],
    },
    "end": {
        "text": ["Day is done.", "Thanks for playing"],
        "choices": [],
    },
}


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global state
    state = "start"
    draw()


def handle_input(pin):
    global state
    if state == "end":
        exit_cb()
        return
    step = STEPS[state]
    if pin == "KEY1" and len(step["choices"]) >= 1:
        state = step["choices"][0][1]
    elif pin == "KEY2" and len(step["choices"]) >= 2:
        state = step["choices"][1][1]
    elif pin == "KEY3" and len(step["choices"]) >= 3:
        state = step["choices"][2][1]
    elif pin == "JOY_PRESS":
        exit_cb()
        return
    draw()


def draw():
    step = STEPS[state]
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    d.text((5, 5), step["text"][0], font=fonts[1], fill=(255, 255, 255))
    d.text((5, 25), step["text"][1], font=fonts[1], fill=(255, 255, 255))
    if step["choices"]:
        y = 70
        for idx, (label, _) in enumerate(step["choices"], 1):
            d.text((5, y), f"{idx}={label}", font=fonts[0], fill=(0, 255, 255))
            y += 12
    else:
        d.text((25, 70), "(Press)", font=fonts[0], fill=(0, 255, 255))
    thread_safe_display(img)
    if state == "end":
        time.sleep(2)
        exit_cb()
