import json
import openai
from PIL import Image, ImageDraw
from .trivia import wrap_text

thread_safe_display = None
fonts = None
exit_cb = None

OPENAI_API_KEY = None
messages = []
conversation = []
current_options = []
text_offset = 0
text_max_offset = 0
line_height = 0


def load_api_key():
    global OPENAI_API_KEY
    try:
        from openai_config import OPENAI_API_KEY as KEY
        OPENAI_API_KEY = KEY
    except Exception:
        OPENAI_API_KEY = "YOUR_API_KEY_HERE"


def request_chat(message):
    """Send the conversation to OpenAI and return reply/options."""
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
                            "You are a friendly assistant. "
                            "After each user message respond with JSON: "
                            "{'reply': '<assistant reply>', 'options': ['choice1','choice2','choice3']} "
                            "where options are short user responses."
                        ),
                    }
                ]
                + messages,
                temperature=0.7,
            )
            txt = resp.choices[0].message["content"].strip()
            data = json.loads(txt)
            if isinstance(data, dict) and "reply" in data and "options" in data:
                messages.append({"role": "assistant", "content": data["reply"]})
                return data
        except Exception:
            messages.pop()  # remove user message if failed
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
    global conversation, current_options, text_offset, messages
    load_api_key()
    messages = []
    data = request_chat("Start the conversation.")
    conversation = ["AI: " + data["reply"]]
    current_options = list(data.get("options", []))
    text_offset = 0
    draw()


def handle_input(pin):
    global conversation, current_options, text_offset
    if pin == "JOY_PRESS":
        exit_cb()
        return
    if pin == "JOY_UP":
        scroll_text(-1)
        return
    if pin == "JOY_DOWN":
        scroll_text(1)
        return
    if pin in ("KEY1", "KEY2", "KEY3"):
        idx = {"KEY1": 0, "KEY2": 1, "KEY3": 2}[pin]
        if idx >= len(current_options):
            return
        user_msg = current_options[idx]
        conversation.append("You: " + user_msg)
        data = request_chat(user_msg)
        conversation.append("AI: " + data["reply"])
        current_options = list(data.get("options", []))
        # keep only recent 20 lines
        if len(conversation) > 20:
            conversation = conversation[-20:]
        text_offset = 0
        draw()


def draw():
    global text_max_offset, line_height, text_offset
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    y = 5 - text_offset
    lines = []
    for line in conversation:
        lines.extend(wrap_text(line, fonts[1], 118, d))
    line_height = fonts[1].getbbox("A")[3] + 2
    total_height = len(lines) * line_height
    text_max_offset = max(0, total_height - 65)
    text_offset = min(text_offset, text_max_offset)
    for line in lines:
        if 5 <= y < 70:
            d.text((5, y), line, font=fonts[1], fill=(255, 255, 255))
        y += line_height
    opt_y = 70
    opt_h = fonts[0].getbbox("A")[3] + 2
    for i, opt in enumerate(current_options, 1):
        d.text((5, opt_y), f"{i}={opt}", font=fonts[0], fill=(0, 255, 255))
        opt_y += opt_h
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

