import json
import openai
from PIL import Image, ImageDraw
from .trivia import wrap_text

thread_safe_display = None
fonts = None
exit_cb = None

OPENAI_API_KEY = None
score = 0
cases_completed = 0
current_case = {}
step_idx = 0
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


def generate_case():
    """Request a new case from OpenAI or return a fallback."""
    if OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_API_KEY_HERE":
        openai.api_key = OPENAI_API_KEY
        prompt = (
            "Create a short veterinary internal medicine scenario for a quiz. "
            "Return JSON with keys intro (2 short sentences), question, options "
            "(3 choices), answer (index 0-2), explanation (one sentence)."
        )
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            txt = resp.choices[0].message["content"].strip()
            data = json.loads(txt)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {
        "intro": [
            "Lucy the Labrador is lethargic and vomiting.",
            "Bloodwork shows elevated liver enzymes."
        ],
        "question": "Which condition is most likely?",
        "options": ["Pancreatitis", "Hepatic lipidosis", "Renal failure"],
        "answer": 0,
        "explanation": "Pancreatitis often causes vomiting with liver enzyme elevation in dogs."
    }


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global score, cases_completed
    load_api_key()
    score = 0
    cases_completed = 0
    next_case()


def next_case():
    global current_case, step_idx, text_offset
    current_case = generate_case()
    step_idx = 0
    text_offset = 0
    draw()


def handle_input(pin):
    global step_idx, text_offset, score, cases_completed
    if pin == "JOY_PRESS":
        exit_cb()
        return
    if pin == "JOY_UP":
        scroll_text(-1)
        return
    if pin == "JOY_DOWN":
        scroll_text(1)
        return
    if step_idx == 0:
        if pin == "KEY1":
            step_idx = 1
            text_offset = 0
            draw()
    elif step_idx == 1:
        if pin == "KEY1":
            choice = 0
        elif pin == "KEY2":
            choice = 1
        elif pin == "KEY3":
            choice = 2
        else:
            return
        if choice == current_case.get("answer", 0):
            score += 1
            feedback = ["Correct!", current_case.get("explanation", "")]
        else:
            feedback = ["Incorrect.", current_case.get("explanation", "")]
        current_case["feedback"] = feedback
        step_idx = 2
        text_offset = 0
        draw()
    elif step_idx == 2:
        if pin == "KEY1":
            cases_completed += 1
            next_case()


def draw():
    global text_max_offset, line_height, text_offset
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    y = 5 - text_offset
    lines = []
    if step_idx == 0:
        for line in current_case.get("intro", []):
            lines.extend(wrap_text(line, fonts[1], 118, d))
        line_height = fonts[1].getbbox("A")[3] + 2
        total_height = len(lines) * line_height
        text_max_offset = max(0, total_height - 65)
        text_offset = min(text_offset, text_max_offset)
        for line in lines:
            if 5 <= y < 70:
                d.text((5, y), line, font=fonts[1], fill=(255, 255, 255))
            y += line_height
        d.text((5, 70), "1=Next", font=fonts[0], fill=(0, 255, 255))
    elif step_idx == 1:
        lines = wrap_text(current_case.get("question", ""), fonts[1], 118, d)
        line_height = fonts[1].getbbox("A")[3] + 2
        total_height = len(lines) * line_height
        text_max_offset = max(0, total_height - 65)
        text_offset = min(text_offset, text_max_offset)
        for line in lines:
            if 5 <= y < 70:
                d.text((5, y), line, font=fonts[1], fill=(255, 255, 0))
            y += line_height
        opt_y = 70
        opt_h = fonts[0].getbbox("A")[3] + 2
        for idx, opt in enumerate(current_case.get("options", []), 1):
            d.text((5, opt_y), f"{idx}={opt}", font=fonts[0], fill=(0, 255, 255))
            opt_y += opt_h
    else:
        for line in current_case.get("feedback", []):
            lines.extend(wrap_text(line, fonts[1], 118, d))
        lines.append(f"Score: {score}/{cases_completed}")
        line_height = fonts[1].getbbox("A")[3] + 2
        total_height = len(lines) * line_height
        text_max_offset = max(0, total_height - 85)
        text_offset = min(text_offset, text_max_offset)
        for line in lines:
            if 5 <= y < 90:
                d.text((5, y), line, font=fonts[1], fill=(255, 255, 255))
            y += line_height
        d.text((5, 90), "1=Continue", font=fonts[0], fill=(0, 255, 255))
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
