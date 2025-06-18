import json
import os
from datetime import datetime

import openai
from PIL import Image, ImageDraw
import time
import threading

from .trivia import wrap_text

# Directory for notes and log file path
NOTES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "notes")
os.makedirs(NOTES_DIR, exist_ok=True)
LOG_PATH = os.path.join(NOTES_DIR, "ailog1.txt")

# Path to the editable system prompt file
PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "systemprompt2.txt")

# Default system prompt used if the text file is missing
DEFAULT_PROMPT = (
        "You are simulating an exaggerated, entertaining day in the life of Gorgina, "
    "the internal medicine referral coordinator at a specialty veterinary clinic. "
    "Gorgina acts as the central coordinator, managing a hectic workload by handling "
    "requests from two internal medicine specialists, Dr. Jodie Anderson and Dr. Molly Doyle, "
    "who frequently send Teams messages requesting patient records from other veterinary clinics. "
    "Gorgina also manages scheduling appointments and conveys messages between clients and doctors "
    "about their pets. She often interacts humorously and warmly with department colleagues, which "
    "include: Dr. Jodie Anderson (DVM), Dr. Molly Doyle (DVM), Mel Miles (CVT), Nova, Maddie Macleod (CVT), "
    "Paul Thomason, and Pablo Miranda. After each scenario respond only with valid JSON containing "
    "keys 'reply' and 'options'. The 'reply' is a short description of the next situation. "
    "The 'options' array must contain exactly three concise numbered actions the user can take. "
    "Avoid trivial choices and maintain engaging, humorous scenarios consistent with the lively "
    "atmosphere of Gorgina’s busy workday."
)


def load_system_prompt() -> str:
    """Read the system prompt text from ``systemprompt.txt`` if available."""
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            text = f.read().strip()
            if text:
                return text
    except Exception as e:
        log(f"Failed to load system prompt: {e}")
    return DEFAULT_PROMPT


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

reveal_thread = None
reveal_stop = threading.Event()
ai_display_len = 0

text_offset = 0
text_max_offset = 0
line_height = 0


def load_api_key():
    """Load the OpenAI API key from env vars or config."""
    global OPENAI_API_KEY
    log("Loading API key", reset=False)

    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        OPENAI_API_KEY = env_key
        log("Loaded API key from environment")
        return

    try:
        from openai_config import OPENAI_API_KEY as KEY
        OPENAI_API_KEY = KEY
        log("Loaded API key from file")
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
        prompt = load_system_prompt()
        log("Sending message to OpenAI")
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
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


def stop_reveal():
    """Stop any ongoing text reveal animation."""
    global reveal_thread, ai_display_len
    if reveal_thread:
        reveal_stop.set()
        reveal_thread.join()
        reveal_thread = None
    if conversation:
        ai_display_len = len(conversation[-1])


def start_reveal():
    """Animate AI text appearing one character at a time."""
    global reveal_thread, ai_display_len

    stop_reveal()

    if not conversation:
        return

    full_text = conversation[-1]

    def task():
        global ai_display_len, reveal_thread
        for i in range(len(full_text)):
            if reveal_stop.is_set():
                break
            ai_display_len = i + 1
            draw(partial=True)
            time.sleep(0.05)
        ai_display_len = len(full_text)
        draw()
        reveal_thread = None

    reveal_stop.clear()
    reveal_thread = threading.Thread(target=task, daemon=True)
    reveal_thread.start()


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    """Begin a new AI Cases session."""
    global conversation, current_options, text_offset, messages, ai_display_len
    log("AI Cases game started", reset=True)
    load_api_key()
    messages = []
    data = request_chat("Start the conversation.")
    # Reset conversation so each scenario appears on a fresh screen
    conversation = [data.get("reply", "")]
    current_options = data.get("options", [])
    text_offset = 0
    ai_display_len = 0
    start_reveal()


def _select_option(num: int):
    """Send the chosen option to the AI and update conversation."""
    global conversation, current_options, text_offset, ai_display_len
    if not current_options:
        exit_cb()
        return
    if num < 1 or num > len(current_options):
        return
    # Replace conversation with the latest choice and response
    conversation = [f"You: {num}"]
    data = request_chat(str(num))
    conversation.append("AI: " + data.get("reply", ""))
    current_options = data.get("options", [])
    text_offset = 0
    ai_display_len = 0
    start_reveal()


def handle_input(pin):
    """Process a hardware button press."""
    stop_reveal()
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


def draw(partial=False):
    global text_max_offset, line_height, text_offset
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)

    kb_y = 128
    y = 5 - text_offset
    lines = []
    for idx, line in enumerate(conversation):
        if partial and idx == len(conversation) - 1:
            line = line[:ai_display_len]
        lines.extend(wrap_text(line, fonts[1], 118, d))
    if not partial:
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
