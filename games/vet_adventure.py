import time
from PIL import Image, ImageDraw

thread_safe_display = None
fonts = None
exit_cb = None

state = "start"

STEPS = {
    "start": {
        "text": ["Gorgina begins", "her day at desk."],
        "choices": [
            ("Check messages", "messages"),
            ("Look at schedule", "schedule"),
            ("Front desk", "front_desk"),
        ],
    },
    "messages": {
        "text": ["Clients left", "several messages."],
        "choices": [
            ("Tell Anderson", "anderson"),
            ("Call client", "call_client"),
            ("Check techs", "tech_room"),
        ],
    },
    "anderson": {
        "text": ["Dr. Anderson", "checks in."],
        "choices": [
            ("Ask for tasks", "anderson_tasks"),
            ("Back to desk", "start"),
        ],
    },
    "anderson_tasks": {
        "text": ["She asks you to", "check on Nova."],
        "choices": [
            ("Find Nova", "find_nova"),
            ("Back", "start"),
        ],
    },
    "find_nova": {
        "text": ["Nova needs help", "calling a client."],
        "choices": [
            ("Assist", "assist_nova"),
            ("Back", "start"),
        ],
    },
    "assist_nova": {
        "text": ["Call goes well,", "Nova relieved."],
        "choices": [
            ("Back to desk", "start"),
        ],
    },
    "tech_room": {
        "text": ["Mel and Maddie", "prep for surgery."],
        "choices": [
            ("Offer help", "offer_help"),
            ("Back", "start"),
        ],
    },
    "offer_help": {
        "text": ["Paul and Pablo", "grab supplies."],
        "choices": [
            ("Return to desk", "start"),
        ],
    },
    "call_client": {
        "text": ["You update the", "client's meds."],
        "choices": [
            ("Record note", "record_note"),
            ("Back", "start"),
        ],
    },
    "record_note": {
        "text": ["Note saved for", "the vets."],
        "choices": [
            ("Wrap up", "wrap_up"),
        ],
    },
    "front_desk": {
        "text": ["Abby steps in,", "adding confusion."],
        "choices": [
            ("Stay firm", "firm"),
            ("Let her", "chaos"),
            ("Back", "start"),
        ],
    },
    "firm": {
        "text": ["Abby sighs and", "backs away."],
        "choices": [
            ("Back to desk", "start"),
        ],
    },
    "chaos": {
        "text": ["Destiny misplaces", "paperwork again."],
        "choices": [
            ("Fix it", "fix_it"),
            ("Back", "start"),
        ],
    },
    "fix_it": {
        "text": ["You fix the mess", "without fuss."],
        "choices": [
            ("Back to desk", "start"),
        ],
    },
    "schedule": {
        "text": ["You review the", "appointment list."],
        "choices": [
            ("Confirm clients", "confirm_apps"),
            ("Find open slot", "open_slot"),
            ("Exam room", "exam_ready"),
        ],
    },
    "confirm_apps": {
        "text": ["Clients confirm or", "reschedule."],
        "choices": [
            ("Mark updated", "wrap_up"),
        ],
    },
    "open_slot": {
        "text": ["3pm slot is", "available today."],
        "choices": [
            ("Tell Doyle", "doyle"),
            ("Leave open", "wrap_up"),
            ("Back", "schedule"),
        ],
    },
    "doyle": {
        "text": ["Dr. Doyle thanks", "you for the info."],
        "choices": [
            ("Back to desk", "wrap_up"),
        ],
    },
    "wrap_up": {
        "text": ["It's nearly 5pm.", "Anything else?"],
        "choices": [
            ("Clock out", "end"),
            ("Check desk", "start"),
        ],
    },
    "exam_ready": {
        "text": ["Maddie signals", "a patient ready."],
        "choices": [
            ("Relay to vet", "relay_vet"),
            ("Get vitals", "vitals"),
            ("Back", "start"),
        ],
    },
    "relay_vet": {
        "text": ["You alert Dr.", "Anderson."],
        "choices": [
            ("Back to desk", "start"),
        ],
    },
    "vitals": {
        "text": ["Paul records the", "vitals with you."],
        "choices": [
            ("Back to desk", "start"),
        ],
    },
    "end": {
        "text": ["5pm hits.", "Time to go home!"],
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
