import time
import random
import threading
from PIL import Image, ImageDraw

from .trivia import QUESTIONS, wrap_text

thread_safe_display = None
fonts = None
exit_cb = None

state = "name1"
player_names = ["Player 1", "Player 2"]
player_scores = [0, 0]
current_name = ""
name_idx = 0
alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ ")

current_topic = None
question_idx = 0
quiz_questions = []

buzzed_player = None
reveal_thread = None
reveal_stop = threading.Event()
question_display_len = 0
question_revealed = False


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global state, player_scores, question_idx, current_name, name_idx
    state = "name1"
    player_scores = [0, 0]
    question_idx = 0
    current_name = ""
    name_idx = 0
    draw_name_input()


def handle_input(pin):
    global state, current_name, name_idx, player_names, current_topic
    global quiz_questions, question_idx, buzzed_player

    if pin == "JOY_PRESS":
        stop_reveal()
        exit_cb()
        return

    if state in ("name1", "name2"):
        if pin == "JOY_LEFT":
            name_idx = (name_idx - 1) % len(alphabet)
        elif pin == "JOY_RIGHT":
            name_idx = (name_idx + 1) % len(alphabet)
        elif pin == "KEY1":
            current_name += alphabet[name_idx]
        elif pin == "KEY2":
            current_name = current_name[:-1]
        elif pin == "KEY3":
            idx = 0 if state == "name1" else 1
            player_names[idx] = current_name or f"Player {idx+1}"
            current_name = ""
            name_idx = 0
            if state == "name1":
                state = "name2"
                draw_name_input()
            else:
                state = "topics"
                draw_topics()
            return
        draw_name_input()
    elif state == "topics":
        if pin == "KEY1":
            current_topic = "Hawaii"
        elif pin == "KEY2":
            current_topic = "Veterinary Internal Medicine"
        else:
            return
        quiz_questions = random.sample(QUESTIONS[current_topic], min(15, len(QUESTIONS[current_topic])))
        question_idx = 0
        player_scores[0] = 0
        player_scores[1] = 0
        state = "question"
        start_question()
    elif state == "question":
        if buzzed_player is None:
            if pin == "JOY_LEFT":
                buzzed_player = 0
                reveal_stop.set()
                draw_question()
            elif pin == "JOY_RIGHT":
                buzzed_player = 1
                reveal_stop.set()
                draw_question()
        else:
            if pin == "KEY1":
                choice = 0
            elif pin == "KEY2":
                choice = 1
            elif pin == "KEY3":
                choice = 2
            else:
                return
            check_answer(choice)


def draw_name_input():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    prompt = "Name for Player 1:" if state == "name1" else "Name for Player 2:"
    d.text((5, 5), prompt, font=fonts[0], fill=(255, 255, 0))
    d.text((5, 40), current_name, font=fonts[1], fill=(0, 255, 255))
    d.text((5, 70), alphabet[name_idx], font=fonts[1], fill=(255, 255, 0))
    d.text((5, 110), "1=Add 2=Del 3=OK", font=fonts[0], fill=(0, 255, 255))
    thread_safe_display(img)


def draw_topics():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    d.text((5, 5), "Trivia Topics", font=fonts[1], fill=(255, 255, 0))
    d.text((5, 40), "1=Hawaii", font=fonts[0], fill=(0, 255, 255))
    d.text((5, 55), "2=Vet Med", font=fonts[0], fill=(0, 255, 255))
    d.text((5, 110), "Press Joy to quit", font=fonts[0], fill=(255, 0, 0))
    thread_safe_display(img)


def start_question():
    global buzzed_player, question_display_len, question_revealed
    buzzed_player = None
    question_display_len = 0
    question_revealed = False
    start_reveal()


def start_reveal():
    global reveal_thread
    stop_reveal()

    def task():
        global question_display_len, question_revealed
        text = quiz_questions[question_idx]["q"]
        for i in range(len(text)):
            if reveal_stop.is_set():
                break
            question_display_len = i + 1
            draw_question(partial=True)
            time.sleep(0.05)
        question_revealed = True
        draw_question()
        reveal_thread = None

    reveal_stop.clear()
    reveal_thread = threading.Thread(target=task, daemon=True)
    reveal_thread.start()


def stop_reveal():
    global reveal_thread
    if reveal_thread:
        reveal_stop.set()
        reveal_thread.join()
        reveal_thread = None


def draw_question(partial=False):
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    q = quiz_questions[question_idx]
    text = q["q"]
    if partial:
        text = text[:question_display_len]
    lines = wrap_text(text, fonts[0], 118, d)
    y = 5
    for line in lines:
        d.text((5, y), line, font=fonts[0], fill=(255, 255, 0))
        y += fonts[0].getbbox("A")[3] + 2
    if not partial:
        for idx, opt in enumerate(q["opts"], 1):
            d.text((5, y), f"{idx}={opt}", font=fonts[0], fill=(0, 255, 255))
            y += fonts[0].getbbox("A")[3] + 2
    d.text((5, 110), f"{player_names[0]}: {player_scores[0]}", font=fonts[0], fill=(0,255,0))
    d.text((70, 110), f"{player_names[1]}: {player_scores[1]}", font=fonts[0], fill=(0,255,0))
    thread_safe_display(img)


def check_answer(choice):
    global question_idx, buzzed_player
    q = quiz_questions[question_idx]
    correct = choice == q["a"]
    correct_opt = q["opts"][q["a"]]
    if correct and buzzed_player is not None:
        player_scores[buzzed_player] += 1
    draw_feedback(correct, correct_opt)
    time.sleep(1)
    question_idx += 1
    if question_idx >= len(quiz_questions):
        draw_final()
        time.sleep(3)
        exit_cb()
    else:
        start_question()


def draw_feedback(correct, correct_opt):
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    if buzzed_player is None:
        text = "No Buzz"
    else:
        text = f"{player_names[buzzed_player]}" \
            + (" Correct" if correct else " Wrong")
    color = (0, 255, 0) if correct else (255, 0, 0)
    d.text((10, 40), text, font=fonts[1], fill=color)
    if not correct:
        d.text((10, 70), f"Ans: {correct_opt}", font=fonts[0], fill=(255,255,0))
    thread_safe_display(img)


def draw_final():
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    d.text((25, 5), "Game Over", font=fonts[1], fill=(255,255,0))
    d.text((5, 40), f"{player_names[0]}: {player_scores[0]}", font=fonts[0], fill=(0,255,255))
    d.text((5, 55), f"{player_names[1]}: {player_scores[1]}", font=fonts[0], fill=(0,255,255))
    if player_scores[0] > player_scores[1]:
        winner = player_names[0]
    elif player_scores[1] > player_scores[0]:
        winner = player_names[1]
    else:
        winner = "Tie"
    d.text((5, 80), f"Winner: {winner}", font=fonts[1], fill=(0,255,0))
    thread_safe_display(img)

