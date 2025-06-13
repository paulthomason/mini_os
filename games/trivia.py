import time
import random
import threading
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

timer_thread = None
timer_stop_event = threading.Event()
timer_end_time = 0

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
        {"q": "Which endocrine test is preferred to confirm canine Addison's disease?", "opts": ["ACTH stimulation", "Low-dose dexamethasone suppression", "Endogenous ACTH"], "a": 0},
        {"q": "The typical radiographic sign of feline asthma is?", "opts": ["Bronchial pattern", "Alveolar pattern", "Interstitial pattern"], "a": 0},
        {"q": "Which antibiotic is recommended for leptospirosis in dogs?", "opts": ["Doxycycline", "Enrofloxacin", "Cephalexin"], "a": 0},
        {"q": "What is the definitive host of Neospora caninum?", "opts": ["Dog", "Cat", "Cow"], "a": 0},
        {"q": "In cats, hepatic lipidosis is most commonly triggered by?", "opts": ["Anorexia", "Hyperthyroidism", "Pancreatitis"], "a": 0},
        {"q": "Which electrolyte imbalance is most characteristic of hypoadrenocorticism?", "opts": ["Low Na and high K", "High Na and low K", "Low Ca and high P"], "a": 0},
        {"q": "Which drug is a potassium-sparing diuretic used for heart failure?", "opts": ["Spironolactone", "Furosemide", "Hydrochlorothiazide"], "a": 0},
        {"q": "A left shift in CBC indicates?", "opts": ["Increased immature neutrophils", "Elevated lymphocytes", "Low platelets"], "a": 0},
        {"q": "Which parasite causes cutaneous larva migrans in humans from dogs?", "opts": ["Ancylostoma", "Toxocara", "Trichuris"], "a": 0},
        {"q": "Most appropriate treatment for feline hyperthyroidism when renal disease precludes radioiodine?", "opts": ["Methimazole", "Thyroidectomy", "No treatment"], "a": 0},
        {"q": "The best test for exocrine pancreatic insufficiency in dogs?", "opts": ["Serum trypsin-like immunoreactivity", "Amylase", "Lipase"], "a": 0},
        {"q": "What is the main vector for cytauxzoonosis in cats?", "opts": ["Amblyomma americanum", "Ctenocephalides felis", "Dermacentor variabilis"], "a": 0},
        {"q": "Which heart murmur grade is described as loud with a precordial thrill?", "opts": ["Grade V", "Grade II", "Grade III"], "a": 0},
        {"q": "What is the most common cause of hypercalcemia in dogs?", "opts": ["Lymphoma", "Chronic kidney disease", "Hypoadrenocorticism"], "a": 0},
        {"q": "Which condition results in muffled heart sounds on auscultation?", "opts": ["Pericardial effusion", "Dilated cardiomyopathy", "Patent ductus arteriosus"], "a": 0},
        {"q": "Which drug is an ACE inhibitor used for proteinuria in cats?", "opts": ["Benazepril", "Metoclopramide", "Maropitant"], "a": 0},
        {"q": "A cat with DCM due to taurine deficiency will most benefit from?", "opts": ["Taurine supplementation", "L-carnitine", "High-protein diet"], "a": 0},
        {"q": "A dog with 'reverse sneezing' likely has irritation of?", "opts": ["Nasopharynx", "Larynx", "Trachea"], "a": 0},
        {"q": "Which fungal pathogen causes nasal lesions in cats and is detected with latex agglutination of serum or urine?", "opts": ["Cryptococcus neoformans", "Histoplasma capsulatum", "Blastomyces dermatitidis"], "a": 0},
        {"q": "Which diagnostic test is most sensitive for early feline renal disease?", "opts": ["SDMA", "Creatinine", "BUN"], "a": 0},
        {"q": "In canine Lyme disease, the protein targeted by most vaccines is?", "opts": ["OspA", "OspB", "OspC"], "a": 0},
        {"q": "Which tick transmits Babesia gibsoni?", "opts": ["Haemaphysalis longicornis", "Ixodes scapularis", "Rhipicephalus sanguineus"], "a": 2},
        {"q": "A 'boot-shaped' heart on radiograph in dogs suggests?", "opts": ["Tetralogy of Fallot", "Pulmonic stenosis", "Atrial septal defect"], "a": 0},
        {"q": "The presence of Heinz bodies in a cat's blood smear is most commonly due to?", "opts": ["Oxidative damage", "Iron deficiency", "Vitamin B12 deficit"], "a": 0},
        {"q": "Which analgesic is contraindicated in cats due to methemoglobinemia risk?", "opts": ["Acetaminophen", "Buprenorphine", "Tramadol"], "a": 0},
        {"q": "What test differentiates regenerative from nonregenerative anemia in dogs?", "opts": ["Reticulocyte count", "Coombs test", "Bone marrow biopsy"], "a": 0},
        {"q": "Which anticoagulant is used to treat feline aortic thromboembolism?", "opts": ["Clopidogrel", "Aspirin", "Apixaban"], "a": 0},
        {"q": "The plication of small intestine is a classic sign in dogs with?", "opts": ["Linear foreign body", "Intussusception", "Parvoviral enteritis"], "a": 0},
        {"q": "Which fluid additive is contraindicated in oliguric renal failure?", "opts": ["Potassium chloride", "Dextrose", "Sodium bicarbonate"], "a": 0},
        {"q": "The mainstay therapy for immune-mediated hemolytic anemia is?", "opts": ["Glucocorticoids", "Antibiotics", "Chemotherapy"], "a": 0},
        {"q": "Which vitamin deficiency is associated with pansteatitis in cats?", "opts": ["Vitamin E", "Vitamin D", "Vitamin K"], "a": 0},
        {"q": "What is the most common clinical sign of hypothyroidism in dogs?", "opts": ["Weight gain", "Polyuria", "Coughing"], "a": 0},
        {"q": "Which diagnostic imaging is best for detecting gallstones in dogs?", "opts": ["Ultrasound", "Radiography", "CT"], "a": 0},
        {"q": "Which breed is predisposed to copper-associated hepatitis due to COMMD1 mutation?", "opts": ["Bedlington Terrier", "Boxer", "Poodle"], "a": 0},
        {"q": "Which medication is contraindicated in cats due to risk of esophageal strictures?", "opts": ["Doxycycline tablets", "Metronidazole", "Clindamycin liquid"], "a": 0},
        {"q": "What is the recommended initial treatment for feline urethral obstruction?", "opts": ["Urethral catheterization", "Perineal urethrostomy", "Renal transplantation"], "a": 0},
        {"q": "Which endocrine disorder in dogs commonly causes a 'potbelly' appearance?", "opts": ["Hyperadrenocorticism", "Hypothyroidism", "Diabetes insipidus"], "a": 0},
        {"q": "What is the drug of choice for acute management of status epilepticus in dogs?", "opts": ["Diazepam", "Phenobarbital", "Levetiracetam"], "a": 0},
        {"q": "In cats, what is the most sensitive test for diagnosing pancreatitis?", "opts": ["Spec fPL", "Amylase", "Trypsin-like immunoreactivity"], "a": 0},
        {"q": "Which metabolic abnormality is most often seen with feline diabetic ketoacidosis?", "opts": ["Metabolic acidosis", "Metabolic alkalosis", "Respiratory alkalosis"], "a": 0},
        {"q": "What is the best method to prevent recurrence of calcium oxalate uroliths in dogs?", "opts": ["Dietary citrate and water intake", "High protein diet", "Calcium supplements"], "a": 0},
        {"q": "Which cat breed is commonly affected by polycystic kidney disease due to PKD1 mutation?", "opts": ["Persian", "Siamese", "Maine Coon"], "a": 0},
        {"q": "A dog diagnosed with degenerative mitral valve disease most benefits from which medication initially?", "opts": ["Pimobendan", "Digoxin", "Atenolol"], "a": 0},
        {"q": "Which antifungal is preferred for treating feline sporotrichosis?", "opts": ["Itraconazole", "Ketoconazole", "Fluconazole"], "a": 0},
        {"q": "What bloodwork abnormality is classic for ethylene glycol toxicity in dogs?", "opts": ["High anion gap metabolic acidosis", "Thrombocytosis", "Hypoglycemia"], "a": 0},
        {"q": "Which antibiotic is recommended for treatment of feline Mycoplasma haemofelis?", "opts": ["Doxycycline", "Penicillin", "Cephalexin"], "a": 0},
        {"q": "What vaccination is recommended annually for cats at risk of upper respiratory disease?", "opts": ["FVRCP", "Rabies", "Panleukopenia only"], "a": 0},
        {"q": "Which parasitic infection leads to ocular migrans in humans from dogs?", "opts": ["Toxocara canis", "Ancylostoma caninum", "Trichuris vulpis"], "a": 0},
    ],
}


def start_timer():
    """Start the countdown timer for answering a question."""
    global timer_thread
    stop_timer()

    def timer_task():
        global timer_thread
        while not timer_stop_event.is_set():
            remaining = timer_end_time - time.time()
            if remaining <= 0:
                break
            draw_question(remaining)
            time.sleep(0.05)
        if not timer_stop_event.is_set():
            handle_time_up()
        timer_thread = None

    timer_stop_event.clear()
    timer_thread = threading.Thread(target=timer_task, daemon=True)
    timer_thread.start()


def stop_timer():
    """Stop the countdown timer."""
    global timer_thread
    if timer_thread:
        timer_stop_event.set()
        timer_thread.join()
        timer_thread = None


def handle_time_up():
    """Handle timer expiration by marking the question wrong."""
    global question_idx, question_offset
    q = quiz_questions[question_idx]
    correct_opt = q["opts"][q["a"]]
    draw_feedback(False, timed_out=True, correct_opt=correct_opt)
    time.sleep(1)
    question_idx += 1
    question_offset = 0
    if question_idx >= len(quiz_questions):
        draw_final()
        time.sleep(3)
        exit_cb()
    else:
        draw_question()
        restart_timer()


def restart_timer():
    global timer_end_time
    timer_end_time = time.time() + 15
    start_timer()


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
        stop_timer()
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
        restart_timer()
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
        stop_timer()
        q = quiz_questions[question_idx]
        correct = choice == q["a"]
        correct_opt = q["opts"][q["a"]]
        if correct:
            score += 1
        draw_feedback(correct, correct_opt=correct_opt)
        time.sleep(1)
        question_idx += 1
        question_offset = 0
        if question_idx >= len(quiz_questions):
            draw_final()
            time.sleep(3)
            exit_cb()
        else:
            draw_question()
            restart_timer()


def draw_topics():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    d.text((5, 5), "Trivia Topics", font=fonts[1], fill=(255, 255, 0))
    d.text((5, 40), "1=Hawaii", font=fonts[0], fill=(0, 255, 255))
    d.text((5, 55), "2=Vet Med", font=fonts[0], fill=(0, 255, 255))
    d.text((5, 110), "Press Joy to quit", font=fonts[0], fill=(255, 0, 0))
    thread_safe_display(img)


def draw_question(time_left=None):
    global question_line_h_small, question_line_h_medium, question_max_offset
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    q = quiz_questions[question_idx]
    dummy = Image.new("RGB", (1, 1))
    dd = ImageDraw.Draw(dummy)
    question_lines = wrap_text(q["q"], fonts[0], 118, dd)
    question_line_h_medium = dd.textbbox((0, 0), "A", font=fonts[0])[3] + 2
    option_line_h = question_line_h_medium
    question_line_h_small = option_line_h

    total_height = len(question_lines) * question_line_h_medium + option_line_h * len(q["opts"]) + 2
    available = 128 - 15
    question_max_offset = max(0, total_height - available)

    y = 15 - question_offset
    for line in question_lines:
        d.text((5, y), line, font=fonts[0], fill=(255, 255, 0))
        y += question_line_h_medium
    y += 2
    for idx, opt in enumerate(q["opts"], 1):
        d.text((5, y), f"{idx}={opt}", font=fonts[0], fill=(0, 255, 255))
        y += option_line_h
    if time_left is not None:
        timer_text = f"{time_left:.2f}"
        bbox = d.textbbox((0, 0), timer_text, font=fonts[1])
        d.text((128 - bbox[2] - 5, 5), timer_text, font=fonts[1], fill=(255, 0, 0))
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


def draw_feedback(correct, timed_out=False, correct_opt=None):
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    if timed_out:
        text = "Time's Up!"
        color = (255, 0, 0)
    else:
        text = "Correct!" if correct else "Wrong!"
        color = (0, 255, 0) if correct else (255, 0, 0)
    d.text((25, 50), text, font=fonts[1], fill=color)
    if not correct and correct_opt:
        d.text((10, 80), f"Ans: {correct_opt}", font=fonts[0], fill=(255, 255, 0))
    thread_safe_display(img)


def draw_final():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    total = len(quiz_questions)
    d.text((25, 40), "Quiz Over", font=fonts[1], fill=(255, 255, 0))
    d.text((20, 70), f"Score: {score}/{total}", font=fonts[1], fill=(0, 255, 255))
    thread_safe_display(img)
