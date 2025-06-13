import random
import time
from PIL import Image, ImageDraw

thread_safe_display = None
fonts = None
exit_cb = None

pet_db = []
current_steps = []
step_idx = 0


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    generate_pet_db()
    next_event()


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


def next_event():
    event = random.choice([appointment_event, message_event, break_event])
    event()


def appointment_event():
    global current_steps, step_idx
    pet = random.choice(pet_db)
    temp = round(random.uniform(100.0, 103.0), 1)
    hr = random.randint(70, 150)
    rr = random.randint(10, 40)
    intro = [f"{pet['name']} {pet['breed']}", f"on {pet['med']}"]
    vitals = [f"T{temp} HR{hr}", f"RR{rr}"]
    current_steps = [
        {"text": intro, "choices": ["Next"], "next": [1]},
        {"text": vitals, "choices": ["Next"], "next": [2]},
        {
            "text": ["Plan?"],
            "choices": ["Bloodwork", "Change med", "Recheck"],
            "next": [3, 3, 3],
        },
        {"text": ["Owner thanks"], "choices": ["Continue"], "next": [-1]},
    ]
    step_idx = 0
    draw()


def message_event():
    global current_steps, step_idx
    pet = random.choice(pet_db)
    messages = [
        {
            "q": "Give more meds?",
            "opts": ["Yes", "No", "See vet"],
        },
        {
            "q": "Not eating well",
            "opts": ["Stop med", "Monitor", "Exam"],
        },
        {
            "q": "Schedule recheck",
            "opts": ["1wk", "2wk", "4wk"],
        },
    ]
    msg = random.choice(messages)
    text = [f"Msg about {pet['name']}", msg["q"]]
    current_steps = [
        {"text": text, "choices": msg["opts"], "next": [1, 1, 1]},
        {"text": ["Client happy"], "choices": ["Continue"], "next": [-1]},
    ]
    step_idx = 0
    draw()


def break_event():
    global current_steps, step_idx
    current_steps = [
        {
            "text": ["Staff wants fun"],
            "choices": ["Play game", "Draw", "Skip"],
            "next": [1, 1, 1],
        },
        {"text": ["Break over"], "choices": ["Continue"], "next": [-1]},
    ]
    step_idx = 0
    draw()


def handle_input(pin):
    global step_idx
    if pin == "JOY_PRESS":
        exit_cb()
        return
    step = current_steps[step_idx]
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
        next_event()
    else:
        step_idx = nxt
        draw()


def draw():
    step = current_steps[step_idx]
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    y = 5
    for line in step["text"]:
        d.text((5, y), line, font=fonts[1], fill=(255, 255, 255))
        y += 20
    if step["choices"]:
        y = 70
        for idx, label in enumerate(step["choices"], 1):
            d.text((5, y), f"{idx}={label}", font=fonts[0], fill=(0, 255, 255))
            y += 12
    else:
        d.text((25, 70), "(Press)", font=fonts[0], fill=(0, 255, 255))
    thread_safe_display(img)
    
