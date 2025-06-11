import time
from PIL import Image, ImageDraw

thread_safe_display = None
fonts = None
exit_cb = None

state = "topics"
current_topic = None
question_idx = 0
score = 0

# Simple text wrapping helper
def wrap_text(text, font, max_width, draw):
    lines = []
    words = text.split()
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

QUESTIONS = {
    "Hawaii": [
        {
            "q": "Which island is called the Big Island?",
            "opts": ["Maui", "Oahu", "Hawaii"],
            "a": 2,
        },
        {
            "q": "State flower of Hawaii?",
            "opts": ["Hibiscus", "Plumeria", "Orchid"],
            "a": 0,
        },
        {
            "q": "Capital city?",
            "opts": ["Honolulu", "Hilo", "Kona"],
            "a": 0,
        },
        {
            "q": "Traditional feast name?",
            "opts": ["Luau", "Hula", "Lei"],
            "a": 0,
        },
        {
            "q": "Volcano National Park is on which island?",
            "opts": ["Kauai", "Hawaii", "Molokai"],
            "a": 1,
        },
        {
            "q": "Largest industry?",
            "opts": ["Agriculture", "Technology", "Tourism"],
            "a": 2,
        },
        {
            "q": "Famous surfing area on Oahu?",
            "opts": ["Waikiki", "North Shore", "Poipu"],
            "a": 1,
        },
        {
            "q": "Hawaii became a U.S. state in?",
            "opts": ["1959", "1965", "1945"],
            "a": 0,
        },
        {
            "q": "Hula is a type of?",
            "opts": ["Dance", "Food", "Boat"],
            "a": 0,
        },
        {
            "q": "Currency used?",
            "opts": ["Dollar", "Peso", "Yen"],
            "a": 0,
        },
        {
            "q": "Pearl Harbor is near?",
            "opts": ["Lahaina", "Honolulu", "Lihue"],
            "a": 1,
        },
        {
            "q": "Popular flower garland?",
            "opts": ["Lei", "Poi", "Wiki"],
            "a": 0,
        },
        {
            "q": "Island known as the Garden Isle?",
            "opts": ["Kauai", "Lanai", "Maui"],
            "a": 0,
        },
        {
            "q": "Famous road on Maui?",
            "opts": ["Hana", "Hilo", "Kona"],
            "a": 0,
        },
        {
            "q": "State fish humuhumunukunukuapua'a is a?",
            "opts": ["Triggerfish", "Tuna", "Shark"],
            "a": 0,
        },
    ],
    "Veterinary Internal Medicine": [
        {
            "q": "Normal dog temp (\u00b0F)?",
            "opts": ["99", "101.5", "103.5"],
            "a": 1,
        },
        {
            "q": "FIV affects which species?",
            "opts": ["Dogs", "Cats", "Horses"],
            "a": 1,
        },
        {
            "q": "Addison's disease involves?",
            "opts": ["Pancreas", "Adrenal", "Thyroid"],
            "a": 1,
        },
        {
            "q": "Common diabetes sign?",
            "opts": ["Hair loss", "Increased thirst", "Limping"],
            "a": 1,
        },
        {
            "q": "Heartworm spread by?",
            "opts": ["Ticks", "Mosquitoes", "Fleas"],
            "a": 1,
        },
        {
            "q": "Treat feline hyperthyroidism with?",
            "opts": ["Insulin", "Methimazole", "Prednisone"],
            "a": 1,
        },
        {
            "q": "Parvo primarily attacks?",
            "opts": ["Intestines", "Liver", "Kidneys"],
            "a": 0,
        },
        {
            "q": "Cushing's disease hormone?",
            "opts": ["Insulin", "Cortisol", "Estrogen"],
            "a": 1,
        },
        {
            "q": "Anemia is low?",
            "opts": ["White cells", "Platelets", "Red cells"],
            "a": 2,
        },
        {
            "q": "FIP stands for feline infectious?",
            "opts": ["Pneumonia", "Peritonitis", "Pancreatitis"],
            "a": 1,
        },
        {
            "q": "Bovine ketosis due to lack of?",
            "opts": ["Calcium", "Energy", "Protein"],
            "a": 1,
        },
        {
            "q": "IMHA stands for immune-mediated?",
            "opts": ["Hepatitis", "Hemolytic anemia", "Heart arrhythmia"],
            "a": 1,
        },
        {
            "q": "Equine colic affects?",
            "opts": ["Lungs", "Digestive tract", "Skin"],
            "a": 1,
        },
        {
            "q": "Common cause of feline CKD?",
            "opts": ["Diabetes", "Age damage", "Heart disease"],
            "a": 1,
        },
        {
            "q": "DHPP vaccine protects distemper, hepatitis, parainfluenza and?",
            "opts": ["Parvo", "Pyometra", "Parrot fever"],
            "a": 0,
        },
    ],
}


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global state
    state = "topics"
    draw_topics()


def handle_input(pin):
    global state, current_topic, question_idx, score
    if pin == "JOY_PRESS":
        exit_cb()
        return
    if state == "topics":
        if pin == "KEY1":
            current_topic = "Hawaii"
        elif pin == "KEY2":
            current_topic = "Veterinary Internal Medicine"
        else:
            return
        question_idx = 0
        score = 0
        state = "question"
        draw_question()
    elif state == "question":
        if pin == "KEY1":
            choice = 0
        elif pin == "KEY2":
            choice = 1
        elif pin == "KEY3":
            choice = 2
        else:
            return
        q = QUESTIONS[current_topic][question_idx]
        correct = choice == q["a"]
        if correct:
            score += 1
        draw_feedback(correct)
        time.sleep(1)
        question_idx += 1
        if question_idx >= len(QUESTIONS[current_topic]):
            draw_final()
            time.sleep(3)
            exit_cb()
        else:
            draw_question()


def draw_topics():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    d.text((5, 5), "Trivia Topics", font=fonts[1], fill=(255, 255, 0))
    d.text((5, 40), "1=Hawaii", font=fonts[0], fill=(0, 255, 255))
    d.text((5, 55), "2=Vet Med", font=fonts[0], fill=(0, 255, 255))
    d.text((5, 110), "Press Joy to quit", font=fonts[0], fill=(255, 0, 0))
    thread_safe_display(img)


def draw_question():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    q = QUESTIONS[current_topic][question_idx]
    d.text(
        (5, 5),
        f"{current_topic} {question_idx + 1}/{len(QUESTIONS[current_topic])}",
        font=fonts[0],
        fill=(255, 255, 255),
    )
    y = 20
    for line in wrap_text(q["q"], fonts[1], 118, d):
        d.text((5, y), line, font=fonts[1], fill=(255, 255, 0))
        y += 14
    y += 2
    for idx, opt in enumerate(q["opts"], 1):
        d.text((5, y), f"{idx}={opt}", font=fonts[0], fill=(0, 255, 255))
        y += 12
    thread_safe_display(img)


def draw_feedback(correct):
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    text = "Correct!" if correct else "Wrong!"
    color = (0, 255, 0) if correct else (255, 0, 0)
    d.text((30, 60), text, font=fonts[1], fill=color)
    thread_safe_display(img)


def draw_final():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    total = len(QUESTIONS[current_topic])
    d.text((25, 40), "Quiz Over", font=fonts[1], fill=(255, 255, 0))
    d.text((20, 70), f"Score: {score}/{total}", font=fonts[1], fill=(0, 255, 255))
    thread_safe_display(img)
