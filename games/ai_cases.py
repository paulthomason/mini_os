import json
import openai
import os
from datetime import datetime
from PIL import Image, ImageDraw
from .trivia import wrap_text

# Directory for notes and log file path
NOTES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "notes")
os.makedirs(NOTES_DIR, exist_ok=True)
LOG_PATH = os.path.join(NOTES_DIR, "ailog1.txt")


def log(message, *, reset=False):
    """Append a timestamped message to the ailog1.txt file."""
    mode = "w" if reset else "a"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_PATH, mode) as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass

thread_safe_display = None
fonts = None
exit_cb = None

OPENAI_API_KEY = None
MISSING_KEY_MSG = (
    "OpenAI API key not found. Please create openai_config.py "
    "with your key to enable chatting."
)
messages = []
conversation = []
typed_text = ""
kb_row = 1
kb_col = 0
keyboard_state = 1  # start with lowercase
keyboard_visible = True

KEYBOARD_UPPER = [
    list("QWERTYUIOP"),
    list("ASDFGHJKL"),
    list("ZXCVBNM"),
    [" "]
]

KEYBOARD_LOWER = [
    list("qwertyuiop"),
    list("asdfghjkl"),
    list("zxcvbnm"),
    [" "]
]

KEYBOARD_PUNCT = [
    list("!@#$%^&*()"),
    list("-_=+[]{}"),
    list(";:'\",.<>/?"),
    [" "]
]

KEYBOARD_NUM = [
    list("1234567890"),
    list("-/:;()$&@\""),
    list(".,?!'[]{}#"),
    [" "]
]

KEY_LAYOUTS = [KEYBOARD_LOWER, KEYBOARD_UPPER, KEYBOARD_PUNCT, KEYBOARD_NUM]
KEY_LAYOUT = KEY_LAYOUTS[keyboard_state]

text_offset = 0
text_max_offset = 0
line_height = 0


def load_api_key():
    global OPENAI_API_KEY
    log("Loading API key", reset=False)
    try:
        from openai_config import OPENAI_API_KEY as KEY
        OPENAI_API_KEY = KEY
        log("Loaded API key successfully")
    except Exception as e:
        OPENAI_API_KEY = None
        log(f"Failed to load API key: {e}")


def request_chat(message):
    """Send the conversation to OpenAI and return reply/options."""
    global messages
    log(f"request_chat called with message: {message}")
    if OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_API_KEY_HERE":
        openai.api_key = OPENAI_API_KEY
        messages.append({"role": "user", "content": message})
        log("Sending message to OpenAI")
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a friendly assistant. "
                            "After each user message respond only with valid JSON "
                            "containing keys 'reply' and 'options'. The reply should "
                            "be your short message to the user. The options array should "
                            "contain up to three short user responses."
                        ),
                    }
                ]
                + messages,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            txt = resp.choices[0].message["content"].strip()
            data = json.loads(txt)
            if isinstance(data, dict) and "reply" in data and "options" in data:
                messages.append({"role": "assistant", "content": data["reply"]})
                log("OpenAI response parsed successfully")
                return data
        except Exception as e:
            messages.pop()  # remove user message if failed
            log(f"OpenAI API call failed: {e}")
    else:
        log("OpenAI API key not configured")
        return {"reply": MISSING_KEY_MSG, "options": []}
    log("Using fallback response")
    return {
        "reply": "Hello! How can I help you?",
        "options": ["Tell me a joke", "How's the weather?", "Bye"],
    }


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global conversation, typed_text, kb_row, kb_col, keyboard_state, KEY_LAYOUT, text_offset, messages, keyboard_visible
    log("AI Cases game started", reset=True)
    load_api_key()
    messages = []
    data = request_chat("Start the conversation.")
    conversation = ["AI: " + data["reply"]]
    typed_text = ""
    kb_row = 1
    kb_col = 0
    keyboard_state = 1
    KEY_LAYOUT = KEY_LAYOUTS[keyboard_state]
    text_offset = 0
    keyboard_visible = True
    draw()


def handle_input(pin):
    global conversation, typed_text, kb_row, kb_col, keyboard_state, KEY_LAYOUT, text_offset, keyboard_visible
    if not keyboard_visible:
        if pin == "JOY_PRESS":
            keyboard_visible = True
            draw()
            return
        if pin == "JOY_UP":
            scroll_text(-1)
            return
        if pin == "JOY_DOWN":
            scroll_text(1)
            return
        return
    if pin == "JOY_PRESS":
        ch = KEY_LAYOUT[kb_row][kb_col]
        typed_text += ch
        draw()
        return
    if pin == "JOY_UP":
        if kb_row > 0:
            kb_row -= 1
        else:
            scroll_text(-1)
        draw()
        return
    if pin == "JOY_DOWN":
        if kb_row < len(KEY_LAYOUT) - 1:
            kb_row += 1
        else:
            scroll_text(1)
        draw()
        return
    if pin == "JOY_LEFT" and kb_col > 0:
        kb_col -= 1
        draw()
        return
    if pin == "JOY_RIGHT" and kb_col < len(KEY_LAYOUT[kb_row]) - 1:
        kb_col += 1
        draw()
        return
    if pin == "KEY1":
        keyboard_state = (keyboard_state + 1) % len(KEY_LAYOUTS)
        KEY_LAYOUT = KEY_LAYOUTS[keyboard_state]
        kb_row = min(kb_row, len(KEY_LAYOUT) - 1)
        kb_col = min(kb_col, len(KEY_LAYOUT[kb_row]) - 1)
        draw()
        return
    if pin == "KEY2":
        typed_text = typed_text[:-1]
        draw()
        return
    if pin == "KEY3":
        if typed_text:
            conversation.append("You: " + typed_text)
            data = request_chat(typed_text)
            conversation.append("AI: " + data["reply"])
            if len(conversation) > 20:
                conversation = conversation[-20:]
            typed_text = ""
            text_offset = 0
            keyboard_visible = False
            draw()
        else:
            exit_cb()
        return


def draw():
    global text_max_offset, line_height, text_offset
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)

    if keyboard_visible:
        kb_y = 70
    else:
        kb_y = 128

    y = 5 - text_offset
    lines = []
    for line in conversation:
        lines.extend(wrap_text(line, fonts[1], 118, d))
    if keyboard_visible or typed_text:
        lines.extend(wrap_text("You: " + typed_text, fonts[1], 118, d))

    line_height = fonts[1].getbbox("A")[3] + 2
    total_height = len(lines) * line_height
    text_max_offset = max(0, total_height - (kb_y - 5))
    text_offset = min(text_offset, text_max_offset)
    for line in lines:
        if 5 <= y < kb_y:
            d.text((5, y), line, font=fonts[1], fill=(255, 255, 255))
        y += line_height

    if keyboard_visible:
        row_h = (128 - kb_y - 10) // len(KEY_LAYOUT)
        key_w = 128 // 10
        for r, row in enumerate(KEY_LAYOUT):
            if r == len(KEY_LAYOUT) - 1 and len(row) == 1:
                ox = 5
                kw = 128 - ox * 2
            else:
                ox = (128 - len(row) * key_w) // 2
                kw = key_w
            for c, ch in enumerate(row):
                x = ox + c * kw
                yk = kb_y + r * row_h
                rect = (x + 1, yk + 1, x + kw - 2, yk + row_h - 2)
                if r == kb_row and c == kb_col:
                    d.rectangle(rect, fill=(0, 255, 0))
                    text_color = (0, 0, 0)
                else:
                    d.rectangle(rect, outline=(255, 255, 255))
                    text_color = (255, 255, 255)
                bbox = d.textbbox((0, 0), ch, font=fonts[0])
                tx = x + (kw - (bbox[2] - bbox[0])) // 2
                ty = yk + (row_h - (bbox[3] - bbox[1])) // 2
                d.text((tx, ty), ch, font=fonts[0], fill=text_color)

        tips = "1=Shift 2=Del 3=Send"
    else:
        tips = "Press stick to type"
    d.text((5, 128 - 10 + 2), tips, font=fonts[0], fill=(0, 255, 255))

    thread_safe_display(img)


def scroll_text(direction):
    global text_offset
    if text_max_offset <= 0:
        return
    prev = text_offset
    text_offset += direction * line_height
    if text_offset < 0:
        text_offset = 0
    if text_offset > text_max_offset:
        text_offset = text_max_offset
    log(f"Scroll from {prev} to {text_offset}")
    draw()

