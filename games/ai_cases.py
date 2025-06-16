import json
import os
from datetime import datetime

import openai
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
current_options = []

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
                            "You are narrating a typical day as a veterinary internal "
                            "medicine specialist. After each scenario respond only with "
                            "valid JSON containing keys 'reply' and 'options'. The reply "
                            "is a short description of the next situation. The options "
                            "array must contain exactly three short numbered choices (1, 2, 3) "
                            "that the user can select to decide what to do next. Use the user's "
                            "previous choice to generate the following scenario."
                        ),
                    }
                ]
                + messages,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            txt = resp.choices[0].message["content"].strip()
            data = json.loads(txt)
            if (
                isinstance(data, dict)
                and "reply" in data
                and isinstance(data.get("options"), list)
                and len(data["options"]) == 3
            ):
                messages.append({"role": "assistant", "content": data["reply"]})
                log("OpenAI response parsed successfully")
                return data
            log("Invalid AI response structure")
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
    """Begin a new AI Cases session."""
    global conversation, current_options, text_offset, messages
    log("AI Cases game started", reset=True)
    load_api_key()
    messages = []
    data = request_chat("Start the conversation.")
    conversation = ["AI: " + data.get("reply", "")] 
    current_options = data.get("options", [])
    text_offset = 0
    draw()


def _select_option(num: int):
    """Send the chosen option to the AI and update conversation."""
    global conversation, current_options, text_offset
    if not current_options:
        exit_cb()
        return
    if num < 1 or num > len(current_options):
        return
    conversation.append(f"You: {num}")
    data = request_chat(str(num))
    conversation.append("AI: " + data.get("reply", ""))
    current_options = data.get("options", [])
    if len(conversation) > 20:
        conversation = conversation[-20:]
    text_offset = 0
    draw()


def handle_input(pin):
    """Process a hardware button press."""
    if pin == "JOY_UP":
        scroll_text(-1)
        return
    if pin == "JOY_DOWN":
        scroll_text(1)
        return
    if pin == "KEY1":
        _select_option(1)
        return
    if pin == "KEY2":
        _select_option(2)
        return
    if pin == "KEY3":
        _select_option(3)
        return


def draw():
    global text_max_offset, line_height, text_offset
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)

    kb_y = 128
    y = 5 - text_offset
    lines = []
    for line in conversation:
        lines.extend(wrap_text(line, fonts[1], 118, d))
    for i, opt in enumerate(current_options, 1):
        lines.extend(wrap_text(f"{i}) {opt}", fonts[1], 118, d))

    line_height = fonts[1].getbbox("A")[3] + 2
    total_height = len(lines) * line_height
    text_max_offset = max(0, total_height - (kb_y - 5))
    text_offset = min(text_offset, text_max_offset)
    for line in lines:
        if 5 <= y < kb_y:
            d.text((5, y), line, font=fonts[1], fill=(255, 255, 255))
        y += line_height

    hint = "Press 1-3 to choose" if current_options else "Press any key to exit"
    d.text((5, 128 - 10 + 2), hint, font=fonts[0], fill=(0, 255, 255))

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

