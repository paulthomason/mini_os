import time
import random
from PIL import Image, ImageDraw

thread_safe_display = None
fonts = None
exit_cb = None

state = "topics"
current_topic = None
question_idx = 0
score = 0
quiz_questions = []
question_offset = 0
question_max_offset = 0
question_line_h_small = 0
question_line_h_medium = 0

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
        {
            "q": "Highest peak in Hawaii?",
            "opts": ["Mauna Kea", "Haleakala", "Diamond Head"],
            "a": 0,
        },
        {
            "q": "Hawaii's state bird?",
            "opts": ["Nene", "Albatross", "Ibis"],
            "a": 0,
        },
        {
            "q": "Island famous for Na Pali Coast?",
            "opts": ["Kauai", "Oahu", "Niihau"],
            "a": 0,
        },
        {
            "q": "Hawaiian word for thank you?",
            "opts": ["Aloha", "Mahalo", "Ono"],
            "a": 1,
        },
        {
            "q": "Time zone of Hawaii?",
            "opts": ["HST", "PST", "MST"],
            "a": 0,
        },
        {
            "q": "Which island has Waimea Canyon?",
            "opts": ["Oahu", "Kauai", "Maui"],
            "a": 1,
        },
        {
            "q": "What instrument often accompanies hula?",
            "opts": ["Ukulele", "Drums", "Violin"],
            "a": 0,
        },
        {
            "q": "Traditional raw fish dish?",
            "opts": ["Poke", "Loco Moco", "Spam musubi"],
            "a": 0,
        },
        {
            "q": "Iolani Palace is in which city?",
            "opts": ["Honolulu", "Lahaina", "Hilo"],
            "a": 0,
        },
        {
            "q": "Hawaii's state tree?",
            "opts": ["Kukui", "Coconut", "Banyan"],
            "a": 0,
        },
        {
            "q": "Which island was the Pineapple Isle?",
            "opts": ["Lanai", "Niihau", "Oahu"],
            "a": 0,
        },
        {
            "q": "Molokini crater is near which island?",
            "opts": ["Maui", "Oahu", "Kauai"],
            "a": 0,
        },
        {
            "q": "Mount Waialeale is found on?",
            "opts": ["Kauai", "Oahu", "Hawaii"],
            "a": 0,
        },
        {
            "q": "Official state sport?",
            "opts": ["Surfing", "Canoeing", "Hiking"],
            "a": 0,
        },
        {
            "q": "Year the monarchy was overthrown?",
            "opts": ["1893", "1880", "1900"],
            "a": 0,
        },
        {
            "q": "Lanai City is on which island?",
            "opts": ["Lanai", "Oahu", "Maui"],
            "a": 0,
        },
        {
            "q": "Haleakala volcano rises on?",
            "opts": ["Maui", "Oahu", "Kauai"],
            "a": 0,
        },
        {
            "q": "Which island is the Forbidden Isle?",
            "opts": ["Niihau", "Lanai", "Kahoolawe"],
            "a": 0,
        },
        {
            "q": "U.S. president born in Honolulu?",
            "opts": ["Barack Obama", "Joe Biden", "John Kennedy"],
            "a": 0,
        },
        {
            "q": "Color of the state flower?",
            "opts": ["Yellow", "Red", "Pink"],
            "a": 0,
        },
        {
            "q": "Highest sea cliffs are on?",
            "opts": ["Molokai", "Hawaii", "Oahu"],
            "a": 0,
        },
        {
            "q": "Largest city on the Big Island?",
            "opts": ["Hilo", "Kona", "Pearl City"],
            "a": 0,
        },
        {
            "q": "Demigod who lassoed the sun?",
            "opts": ["Maui", "Pele", "Hiiaka"],
            "a": 0,
        },
        {
            "q": "Meal of rice, burger, egg & gravy?",
            "opts": ["Loco Moco", "Poke", "Manapua"],
            "a": 0,
        },
        {
            "q": "Kalaupapa leprosy colony is on?",
            "opts": ["Molokai", "Maui", "Oahu"],
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
        {
            "q": "Pancreatitis diagnosed best with?",
            "opts": ["X-ray", "Ultrasound", "MRI"],
            "a": 1,
        },
        {
            "q": "Common sign of feline hyperthyroidism?",
            "opts": ["Weight gain", "Weight loss", "Seizures"],
            "a": 1,
        },
        {
            "q": "GDV stands for?",
            "opts": ["Gastric Dilatation Volvulus", "Generalized Dermatitis Virus", "Giant Dog Vomit"],
            "a": 0,
        },
        {
            "q": "Renal failure leads to high?",
            "opts": ["Blood urea nitrogen", "Glucose", "Calcium"],
            "a": 0,
        },
        {
            "q": "A common tick-borne disease in dogs?",
            "opts": ["Leptospirosis", "Lyme disease", "Distemper"],
            "a": 1,
        },
        {
            "q": "Causative agent of toxoplasmosis?",
            "opts": ["Toxoplasma gondii", "Giardia", "Coccidia"],
            "a": 0,
        },
        {
            "q": "Hormone lacking in diabetes mellitus?",
            "opts": ["Insulin", "Cortisol", "Thyroxine"],
            "a": 0,
        },
        {
            "q": "Primary cause of canine Cushing's?",
            "opts": ["Pituitary tumor", "Adrenal atrophy", "Kidney disease"],
            "a": 0,
        },
        {
            "q": "Normal cat heart rate?",
            "opts": ["120-160", "60-90", "40-60"],
            "a": 0,
        },
        {
            "q": "Common cause of canine seizures?",
            "opts": ["Epilepsy", "Hyperkalemia", "Hypothyroidism"],
            "a": 0,
        },
        {
            "q": "Heartworm prevention drug?",
            "opts": ["Ivermectin", "Amoxicillin", "Prednisone"],
            "a": 0,
        },
        {
            "q": "Test used to detect FeLV?",
            "opts": ["Snap ELISA", "Fecal float", "CT scan"],
            "a": 0,
        },
        {
            "q": "Panleukopenia affects primarily?",
            "opts": ["Cats", "Dogs", "Horses"],
            "a": 0,
        },
        {
            "q": "Leptospirosis damages which organ most?",
            "opts": ["Kidneys", "Heart", "Lungs"],
            "a": 0,
        },
        {
            "q": "Treatment for canine hypothyroidism?",
            "opts": ["Levothyroxine", "Insulin", "Progesterone"],
            "a": 0,
        },
        {
            "q": "CBC stands for?",
            "opts": ["Complete Blood Count", "Critical Body Condition", "Calcium Binding Complex"],
            "a": 0,
        },
        {
            "q": "Breed prone to dilated cardiomyopathy?",
            "opts": ["Doberman", "Chihuahua", "Pug"],
            "a": 0,
        },
        {
            "q": "Drug of choice for status epilepticus?",
            "opts": ["Diazepam", "Hydrocodone", "Carprofen"],
            "a": 0,
        },
        {
            "q": "Pyometra is a?",
            "opts": ["Uterine infection", "Ear infection", "Bone cancer"],
            "a": 0,
        },
        {
            "q": "Nutrient restricted in renal diets?",
            "opts": ["Phosphorus", "Fat", "Carbohydrate"],
            "a": 0,
        },
        {
            "q": "Cattle bloat affects which compartment?",
            "opts": ["Rumen", "Abomasum", "Omasum"],
            "a": 0,
        },
        {
            "q": "Medication for feline asthma?",
            "opts": ["Bronchodilator", "Insulin", "Diuretic"],
            "a": 0,
        },
        {
            "q": "Addison's disease treated with?",
            "opts": ["Steroids", "Antibiotics", "Insulin"],
            "a": 0,
        },
        {
            "q": "PCR test detects?",
            "opts": ["DNA/RNA", "Proteins", "Electrolytes"],
            "a": 0,
        },
        {
            "q": "Which organ is affected by hepatitis?",
            "opts": ["Liver", "Heart", "Spleen"],
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
    global state, current_topic, question_idx, score, quiz_questions, question_offset
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
        quiz_questions = random.sample(QUESTIONS[current_topic], min(15, len(QUESTIONS[current_topic])))
        question_offset = 0
        state = "question"
        draw_question()
    elif state == "question":
        if pin == "KEY1":
            choice = 0
        elif pin == "KEY2":
            choice = 1
        elif pin == "KEY3":
            choice = 2
        elif pin == "JOY_UP":
            scroll_question(-1)
            return
        elif pin == "JOY_DOWN":
            scroll_question(1)
            return
        else:
            return
        q = quiz_questions[question_idx]
        correct = choice == q["a"]
        if correct:
            score += 1
        draw_feedback(correct)
        time.sleep(1)
        question_idx += 1
        question_offset = 0
        if question_idx >= len(quiz_questions):
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
    global question_line_h_small, question_line_h_medium, question_max_offset
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    q = quiz_questions[question_idx]
    d.text(
        (5, 5),
        f"{current_topic} {question_idx + 1}/{len(quiz_questions)}",
        font=fonts[0],
        fill=(255, 255, 255),
    )

    dummy = Image.new("RGB", (1, 1))
    dd = ImageDraw.Draw(dummy)
    question_lines = wrap_text(q["q"], fonts[1], 118, dd)
    question_line_h_medium = dd.textbbox((0, 0), "A", font=fonts[1])[3] + 2
    option_line_h = dd.textbbox((0, 0), "A", font=fonts[0])[3] + 2
    question_line_h_small = option_line_h

    total_height = len(question_lines) * question_line_h_medium + option_line_h * len(q["opts"]) + 2
    available = 128 - 20
    question_max_offset = max(0, total_height - available)

    y = 20 - question_offset
    for line in question_lines:
        d.text((5, y), line, font=fonts[1], fill=(255, 255, 0))
        y += question_line_h_medium
    y += 2
    for idx, opt in enumerate(q["opts"], 1):
        d.text((5, y), f"{idx}={opt}", font=fonts[0], fill=(0, 255, 255))
        y += option_line_h
    thread_safe_display(img)


def scroll_question(direction):
    global question_offset
    if question_max_offset <= 0:
        return
    step = min(question_line_h_small, question_line_h_medium)
    question_offset += direction * step
    if question_offset < 0:
        question_offset = 0
    if question_offset > question_max_offset:
        question_offset = question_max_offset
    draw_question()


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
    total = len(quiz_questions)
    d.text((25, 40), "Quiz Over", font=fonts[1], fill=(255, 255, 0))
    d.text((20, 70), f"Score: {score}/{total}", font=fonts[1], fill=(0, 255, 255))
    thread_safe_display(img)
