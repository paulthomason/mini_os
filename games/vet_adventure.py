import json
import os
import time
import openai
from datetime import datetime
from PIL import Image, ImageDraw
from .trivia import wrap_text

thread_safe_display = None
fonts = None
exit_cb = None

OPENAI_API_KEY = None
MISSING_KEY_MSG = (
    "OpenAI API key not found. Please create openai_config.py with your key."
)

messages = []
conversation = []
current_options = []
text_offset = 0
text_max_offset = 0
line_height = 0
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "notes", "vet_ai_log.txt")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

def log(msg, *, reset=False):
    mode = "w" if reset else "a"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_PATH, mode) as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

def load_api_key():
    """Populate OPENAI_API_KEY from env vars or config files."""
    global OPENAI_API_KEY

    # Environment variable takes precedence so deployments can avoid
    # storing secrets in source control.
    env_key = os.environ.get("VA_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if env_key:
        OPENAI_API_KEY = env_key
        return

    try:
        from vet_openai_config import VA_OPENAI_API_KEY as KEY
        OPENAI_API_KEY = KEY
    except Exception:
        try:
            from openai_config import OPENAI_API_KEY as KEY
            OPENAI_API_KEY = KEY
        except Exception as e:
            OPENAI_API_KEY = None
            log(f"API key load failed: {e}")

def request_chat(message):
    global messages
    if OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_API_KEY_HERE":
        openai.api_key = OPENAI_API_KEY
        messages.append({"role": "user", "content": message})
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You narrate an amusing text adventure set in a busy veterinary clinic. "
                            "After each short scene respond ONLY with JSON containing keys 'reply' and 'options'. "
                            "Provide exactly three numbered choices in 'options'."
                        ),
                    }
                ] + messages,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message["content"].strip())
            if isinstance(data, dict) and "reply" in data and isinstance(data.get("options"), list):
                messages.append({"role": "assistant", "content": data["reply"]})
                return data
        except Exception as e:
            messages.pop()
            log(f"OpenAI request failed: {e}")
    return {"reply": MISSING_KEY_MSG, "options": []}

def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback

def start():
    global conversation, current_options, text_offset, messages
    log("Vet Adventure started", reset=True)
    load_api_key()
    messages = []
    data = request_chat("Start the adventure.")
    conversation = ["AI: " + data.get("reply", "")]
    current_options = data.get("options", [])
    text_offset = 0
    draw()

def _select_option(num):
    global conversation, current_options, text_offset
    if not current_options:
        exit_cb()
        return
    if num < 1 or num > len(current_options):
        return
    conversation = [f"You: {num}"]
    data = request_chat(str(num))
    conversation.append("AI: " + data.get("reply", ""))
    current_options = data.get("options", [])
    text_offset = 0
    draw()

def handle_input(pin):
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
    if pin == "JOY_PRESS":
        exit_cb()


def draw():
    global text_max_offset, line_height, text_offset
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    y = 5 - text_offset
    lines = []
    for line in conversation:
        lines.extend(wrap_text(line, fonts[1], 118, d))
    for i, opt in enumerate(current_options, 1):
        lines.extend(wrap_text(f"{i}) {opt}", fonts[1], 118, d))
    line_height = fonts[1].getbbox("A")[3] + 2
    total_height = len(lines) * line_height
    text_max_offset = max(0, total_height - (128 - 10))
    text_offset = min(text_offset, text_max_offset)
    for line in lines:
        if 5 <= y < 128:
            d.text((5, y), line, font=fonts[1], fill=(255, 255, 255))
        y += line_height
    hint = "Press 1-3 to choose" if current_options else "Press any key to exit"
    d.text((5, 118), hint, font=fonts[0], fill=(0, 255, 255))
    thread_safe_display(img)

def scroll_text(direction):
    global text_offset
    if text_max_offset <= 0:
        return
    text_offset += direction * line_height
    if text_offset < 0:
        text_offset = 0
    if text_offset > text_max_offset:
        text_offset = text_max_offset
    draw()
