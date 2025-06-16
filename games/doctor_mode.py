import random
from PIL import Image, ImageDraw
from .trivia import wrap_text

thread_safe_display = None
fonts = None
exit_cb = None

# Templates for interactive training cases.  Each function accepts a pet
# dictionary and returns a scenario dict used to build dialogue steps.

def scenario_vaccine(pet):
    return {
        "intro": [
            f"{pet['name']} the {pet['breed']} is in for vaccines.",
            "Owner wonders if the distemper booster is needed annually.",
        ],
        "question": "How often should adult dogs receive the distemper booster?",
        "options": ["Every year", "Every three years", "Only as puppies"],
        "answer": 1,
        "explanation": (
            "After the initial puppy series, most core vaccines like distemper "
            "are typically boosted every three years."
        ),
        "closing": "Owner thanks you for clarifying vaccine schedules.",
    }


def scenario_pain_med(pet):
    return {
        "intro": [
            f"{pet['name']} is on {pet['med']} for {pet['disease']}.",
            "Owner asks about giving ibuprofen for pain.",
        ],
        "question": "Is ibuprofen safe for dogs?",
        "options": ["Yes, it's fine", "No, it can be toxic", "Only with food"],
        "answer": 1,
        "explanation": (
            "Ibuprofen can cause gastric ulcers and kidney damage in dogs. Use a "
            "veterinarian-prescribed medication instead."
        ),
        "closing": "You recommend an approved canine pain medication.",
    }


def scenario_hyperthyroid(pet):
    return {
        "intro": [
            f"{pet['name']} the {pet['breed']} has been losing weight.",
            "You suspect hyperthyroidism.",
        ],
        "question": "Which blood test confirms feline hyperthyroidism?",
        "options": ["Total T4 level", "BUN/Creatinine", "Blood glucose"],
        "answer": 0,
        "explanation": (
            "An elevated total T4 concentration is most consistent with feline "
            "hyperthyroidism."
        ),
        "closing": "Owner agrees to proceed with bloodwork.",
    }


def scenario_heartworm(pet):
    return {
        "intro": [
            f"{pet['name']} returned from travel and is now coughing.",
            "Heartworm disease is a concern.",
        ],
        "question": "What screening test is commonly used for canine heartworm?",
        "options": ["Fecal exam", "Antigen blood test", "Chest radiographs"],
        "answer": 1,
        "explanation": (
            "The antigen blood test detects proteins from adult female "
            "heartworms and is the standard screening method."
        ),
        "closing": "A sample is collected for testing.",
    }


def scenario_missed_med(pet):
    return {
        "intro": [
            f"{pet['name']} is on {pet['med']}.",
            "Owner skipped a dose and gave double the next time.",
        ],
        "question": "What should you advise the owner?",
        "options": [
            "Continue with the regular schedule",
            "Stop the medication",
            "Double doses next time too",
        ],
        "answer": 0,
        "explanation": (
            "Generally the missed dose should not be doubled. Resume the regular "
            "schedule unless problems occur."
        ),
        "closing": "Owner understands to continue normally.",
    }


SCENARIOS = [
    scenario_vaccine,
    scenario_pain_med,
    scenario_hyperthyroid,
    scenario_heartworm,
    scenario_missed_med,
]


pet_db = []
current_steps = []
step_idx = 0
text_offset = 0
text_max_offset = 0
line_height = 0


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    """Initialize the pet database and launch the first training case."""
    generate_pet_db()
    next_case()


def generate_pet_db():
    global pet_db
    names_dog = ["Fido", "Buddy", "Max", "Rocky", "Cooper"]
    names_cat = ["Luna", "Milo", "Bella", "Oliver", "Kitty"]
    dog_breeds = [
        ("Labrador", "ear infection", "otic drops"),
        ("German Shep", "hip dysplasia", "carprofen"),
        ("Golden Ret", "allergies", "apoquel"),
        ("Dachshund", "back pain", "prednisone"),
        ("Boxer", "heart dz", "enalapril"),
    ]
    cat_breeds = [
        ("DSH", "hyperthyroid", "methimazole"),
        ("Maine Coon", "heart dz", "atenolol"),
        ("Siamese", "asthma", "fluticasone"),
        ("Persian", "kidney dz", "enalapril"),
        ("Sphynx", "skin infection", "antibiotics"),
    ]
    pet_db = []
    for _ in range(3):
        breed, disease, med = random.choice(dog_breeds)
        pet_db.append({
            "name": random.choice(names_dog),
            "species": "dog",
            "breed": breed,
            "age": random.randint(1, 12),
            "sex": random.choice(["M", "F"]),
            "disease": disease,
            "med": med,
        })
        breed, disease, med = random.choice(cat_breeds)
        pet_db.append({
            "name": random.choice(names_cat),
            "species": "cat",
            "breed": breed,
            "age": random.randint(1, 15),
            "sex": random.choice(["M", "F"]),
            "disease": disease,
            "med": med,
        })


def next_case():
    """Select a random training scenario and build dialogue steps."""
    global current_steps, step_idx, text_offset
    pet = random.choice(pet_db)
    template = random.choice(SCENARIOS)
    case = template(pet)
    current_steps = [
        {"text": case["intro"], "choices": ["Next"], "next": [1]},
        {
            "text": [case["question"]],
            "choices": case["options"],
            "answer": case["answer"],
            "explanation": case["explanation"],
            "next": [2, 2, 2],
        },
        {"text": [""], "choices": ["Next"], "next": [3]},
        {"text": [case.get("closing", "Case complete.")], "choices": ["Continue"], "next": [-1]},
    ]
    step_idx = 0
    text_offset = 0
    draw()




def handle_input(pin):
    global step_idx, text_offset
    if pin == "JOY_PRESS":
        exit_cb()
        return
    if pin == "JOY_UP":
        scroll_text(-1)
        return
    elif pin == "JOY_DOWN":
        scroll_text(1)
        return
    step = current_steps[step_idx]
    # If this step contains a quiz question, evaluate the response
    if "answer" in step:
        if pin == "KEY1":
            choice = 0
        elif pin == "KEY2" and len(step["choices"]) >= 2:
            choice = 1
        elif pin == "KEY3" and len(step["choices"]) >= 3:
            choice = 2
        else:
            return
        if choice == step["answer"]:
            current_steps[2]["text"] = ["Correct!"]
        else:
            current_steps[2]["text"] = ["Hold on...", step["explanation"]]
        step_idx = 2
        draw()
        return
    if not step["choices"]:
        if pin == "KEY1":
            nxt = step.get("next", -1)
        else:
            return
    else:
        if pin == "KEY1":
            nxt = step["next"][0]
        elif pin == "KEY2" and len(step["choices"]) >= 2:
            nxt = step["next"][1]
        elif pin == "KEY3" and len(step["choices"]) >= 3:
            nxt = step["next"][2]
        else:
            return
    if nxt == -1:
        next_case()
    else:
        step_idx = nxt
        text_offset = 0
        draw()


def draw():
    global text_max_offset, line_height, text_offset
    step = current_steps[step_idx]
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    y = 5 - text_offset
    lines = []
    for line in step["text"]:
        lines.extend(wrap_text(line, fonts[1], 118, d))
    line_height = fonts[1].getbbox("A")[3] + 2
    total_height = len(lines) * line_height
    available = 70 - 5
    text_max_offset = max(0, total_height - available)
    text_offset = min(text_offset, text_max_offset)
    for line in lines:
        if 5 <= y < 70:
            d.text((5, y), line, font=fonts[1], fill=(255, 255, 255))
        y += line_height
    if step["choices"]:
        y = 70
        opt_h = fonts[0].getbbox("A")[3] + 2
        for idx, label in enumerate(step["choices"], 1):
            d.text((5, y), f"{idx}={label}", font=fonts[0], fill=(0, 255, 255))
            y += opt_h
    else:
        d.text((25, 70), "(Press)", font=fonts[0], fill=(0, 255, 255))
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
    
