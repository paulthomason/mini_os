import time
from PIL import Image, ImageDraw

thread_safe_display = None
fonts = None
exit_cb = None

current_topic = None
question_index = 0
score = 0
state = "topic"

QUESTION_BANK = {
    "Hawaii": [
        {"q": "Capital of Hawaii?", "choices": ["Honolulu", "Hilo", "Kona"], "answer": 0},
        {"q": "How many main islands?", "choices": ["5", "8", "12"], "answer": 1},
        {"q": "Traditional dance?", "choices": ["Tango", "Hula", "Salsa"], "answer": 1},
        {"q": "Volcanoes NP island?", "choices": ["Maui", "Oahu", "Hawaii"], "answer": 2},
        {"q": "State fish?", "choices": ["Mahi Mahi", "Humuhumunukunukuapuaa", "Ahi"], "answer": 1},
        {"q": "Highest peak?", "choices": ["Mauna Kea", "Haleakala", "Mauna Loa"], "answer": 0},
        {"q": "Ocean around Hawaii?", "choices": ["Indian", "Pacific", "Atlantic"], "answer": 1},
        {"q": "Famous Oahu beach?", "choices": ["Waikiki", "Bondi", "Venice"], "answer": 0},
        {"q": "Statehood year?", "choices": ["1959", "1915", "1972"], "answer": 0},
        {"q": "Word for hello?", "choices": ["Aloha", "Mahalo", "Hola"], "answer": 0},
        {"q": "Time zone?", "choices": ["Pacific", "Hawaiian", "Central"], "answer": 1},
        {"q": "USS Arizona Memorial?", "choices": ["Pearl Harbor", "Lahaina", "Hilo"], "answer": 0},
        {"q": "Biggest industry?", "choices": ["Agriculture", "Tourism", "Mining"], "answer": 1},
        {"q": "Garden Isle?", "choices": ["Kauai", "Molokai", "Lanai"], "answer": 0},
        {"q": "Welcome garland?", "choices": ["Lei", "Tiara", "Wreath"], "answer": 0},
    ],
    "Veterinary Internal Medicine": [
        {"q": "Dog heartworm?", "choices": ["Dirofilaria immitis", "Ancylostoma caninum", "Dipylidium"], "answer": 0},
        {"q": "Cushing's excess of?", "choices": ["Thyroxine", "Cortisol", "Insulin"], "answer": 1},
        {"q": "Cat hyperthyroid cause?", "choices": ["Renal failure", "Adenomatous hyperplasia", "Iodine deficiency"], "answer": 1},
        {"q": "Insulin-secreting tumor?", "choices": ["Lymphoma", "Insulinoma", "Hemangioma"], "answer": 1},
        {"q": "Addison's is lack of?", "choices": ["Adrenal hormones", "Thyroxine", "Insulin"], "answer": 0},
        {"q": "FIP stands for?", "choices": ["Feline infectious peritonitis", "Feline intestinal parasites", "Feline immunologic problem"], "answer": 0},
        {"q": "Best urine sample?", "choices": ["Voided", "Cystocentesis", "Floor swab"], "answer": 1},
        {"q": "Shock fluid choice?", "choices": ["5% dextrose", "Isotonic crystalloids", "Hypertonic saline"], "answer": 1},
        {"q": "Specific liver enzyme?", "choices": ["ALT", "CK", "Lipase"], "answer": 0},
        {"q": "Image heart chambers?", "choices": ["CT", "Radiography", "Echocardiography"], "answer": 2},
        {"q": "FeLV means?", "choices": ["Feline leukemia virus", "Feline liver virus", "Feline laryngeal virus"], "answer": 0},
        {"q": "GDV abbreviation?", "choices": ["General dermatitis", "Gastric dilatation-volvulus", "Glandular dysplasia"], "answer": 1},
        {"q": "Diabetes insipidus sign?", "choices": ["Polyuria/polydipsia", "Alopecia", "Hematuria"], "answer": 0},
        {"q": "Pancreatitis test?", "choices": ["Spec cPL", "Creatinine", "ALT"], "answer": 0},
        {"q": "Furosemide class?", "choices": ["Diuretic", "Analgesic", "Steroid"], "answer": 0},
    ],
}


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global state
    state = "topic"
    draw_topic_select()


def handle_input(pin):
    global state, current_topic, question_index, score
    if state == "topic":
        if pin == "KEY1":
            current_topic = "Hawaii"
            question_index = 0
            score = 0
            state = "quiz"
            draw_question()
        elif pin == "KEY2":
            current_topic = "Veterinary Internal Medicine"
            question_index = 0
            score = 0
            state = "quiz"
            draw_question()
        elif pin in ("JOY_PRESS", "KEY3"):
            exit_cb()
    elif state == "quiz":
        if pin in ("KEY1", "KEY2", "KEY3"):
            choice = {"KEY1": 0, "KEY2": 1, "KEY3": 2}[pin]
            q = QUESTION_BANK[current_topic][question_index]
            if choice == q["answer"]:
                score += 1
            question_index += 1
            if question_index >= len(QUESTION_BANK[current_topic]):
                draw_score()
                time.sleep(2)
                exit_cb()
            else:
                draw_question()
        elif pin == "JOY_PRESS":
            exit_cb()


def draw_topic_select():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    d.text((10, 5), "Select Topic", font=fonts[1], fill=(255, 255, 255))
    d.text((10, 40), "1=Hawaii", font=fonts[0], fill=(0, 255, 0))
    d.text((10, 55), "2=Vet Med", font=fonts[0], fill=(0, 255, 0))
    d.text((10, 90), "Press Joy to exit", font=fonts[0], fill=(255, 0, 0))
    thread_safe_display(img)


def draw_question():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    q = QUESTION_BANK[current_topic][question_index]
    d.text((5, 5), f"Q{question_index + 1}: {q['q']}", font=fonts[0], fill=(255, 255, 255))
    d.text((5, 40), f"1 {q['choices'][0]}", font=fonts[0], fill=(0, 255, 0))
    d.text((5, 55), f"2 {q['choices'][1]}", font=fonts[0], fill=(0, 255, 0))
    d.text((5, 70), f"3 {q['choices'][2]}", font=fonts[0], fill=(0, 255, 0))
    thread_safe_display(img)


def draw_score():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    total = len(QUESTION_BANK[current_topic])
    d.text((20, 50), f"Score {score}/{total}", font=fonts[1], fill=(255, 255, 0))
    thread_safe_display(img)
