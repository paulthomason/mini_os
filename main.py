#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time
import subprocess
from datetime import datetime
import os
import random
import threading
import requests
import re
import webbrowser
import shutil
import socket
from games import snake, tetris, rps, space_invaders, vet_adventure, axe, trivia

# Luma.lcd imports and setup
from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.lcd.device import st7735
from PIL import ImageFont, ImageDraw, Image

# --- Display Configuration ---
# Waveshare 1.44inch LCD HAT with ST7735S controller is 128x128 pixels. 
# h_offset and v_offset may need fine-tuning for perfect centering on some displays.
# The Waveshare display's horizontal direction starts from the second pixel, so h_offset=2 might be needed. 
# bgr=True is common for ST7735S displays.
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 128
KEYBOARD_OFFSET = 8  # Pixels to shift on-screen keyboard up

# Pin configuration for luma.lcd
RST_PIN = 27  # GPIO 27 
DC_PIN = 25   # GPIO 25 
# CS (GPIO 8), SCLK (GPIO 11), MOSI (GPIO 10) are handled by the SPI interface directly. 
BL_PIN = 24   # Backlight pin, GPIO 24 

# SPI communication setup (port=0, device=0 corresponds to SPI0 CE0/GPIO 8)
# Speed can be up to 60MHz for ST7735S 
serial_interface = spi(port=0, device=0,
                       gpio_DC=DC_PIN, gpio_RST=RST_PIN,
                       speed_hz=16000000) # 16MHz is a good speed. Max is 60MHz.

# LCD device initialization. bgr=True is important for correct colors on many ST7735 displays.
# h_offset/v_offset may need minor tuning for perfect alignment on 128x128 physical screens,
# as the ST7735S has a native resolution of 132x162, and the Waveshare HAT uses a 128x128 portion. 
device = st7735(serial_interface, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, bgr=True,
                h_offset=2, v_offset=1) # Adjust offsets if your display has borders/misalignment

# Ensure display access is thread-safe
display_lock = threading.Lock()

def thread_safe_display(img):
    with display_lock:
        device.display(img)

# --- Joystick and Button Configuration ---
# GPIO setup using BCM numbering. Buttons are active LOW (pressed = low).
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

BUTTON_PINS = {
    "KEY1": 21, "KEY2": 20, "KEY3": 16, # General purpose buttons 
    "JOY_UP": 6, "JOY_DOWN": 19, "JOY_LEFT": 5, "JOY_RIGHT": 26, "JOY_PRESS": 13 # Joystick directions and press 
}

# Set up each pin as an input with an internal pull-up resistor
for pin_name, pin_num in BUTTON_PINS.items():
    GPIO.setup(pin_num, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Global dictionary to track button states (updated by callback)
button_states = {name: False for name in BUTTON_PINS.keys()}
last_event_time = {name: 0.0 for name in BUTTON_PINS.keys()} # For basic debounce

# Friendly names for buttons/joystick used in the reaction game
BUTTON_NAMES = {
    "JOY_UP": "Joystick Up",
    "JOY_DOWN": "Joystick Down",
    "JOY_LEFT": "Joystick Left",
    "JOY_RIGHT": "Joystick Right",
    "JOY_PRESS": "Joystick Press",
    "KEY1": "Button 1",
    "KEY2": "Button 2",
    "KEY3": "Button 3",
}

# Reaction game state
game_round = 0
game_score = 0
game_prompt = None

# Timer support for the reaction game
timer_thread = None
timer_stop_event = threading.Event()
timer_end_time = 0

# --- Fonts ---
# Support choosing different fonts and text sizes.
AVAILABLE_FONTS = {
    "DejaVu Sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVu Serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "DejaVu Sans Mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
}

TEXT_SIZE_MAP = {
    "Small": (9, 11, 13),
    "Medium": (11, 13, 15),
    "Large": (13, 15, 18),
}

current_font_name = "DejaVu Sans"
current_text_size = "Medium"


def update_fonts():
    """Reload fonts based on the selected font and size."""
    global font_small, font_medium, font_large
    sizes = TEXT_SIZE_MAP.get(current_text_size, TEXT_SIZE_MAP["Medium"])
    font_path = AVAILABLE_FONTS.get(current_font_name, list(AVAILABLE_FONTS.values())[0])
    try:
        font_small = ImageFont.truetype(font_path, sizes[0])
        font_medium = ImageFont.truetype(font_path, sizes[1])
        font_large = ImageFont.truetype(font_path, sizes[2])
    except IOError:
        print("Defaulting to built-in fonts.")
        font_small = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_large = ImageFont.load_default()


update_fonts()

# --- Backlight Control ---
brightness_level = 100  # Percentage 0-100
backlight_pwm = None

# --- NYT Top Stories ---
nyt_stories = []
current_story_index = 0
story_lines = []          # Wrapped lines of the currently viewed story
story_line_h = 0          # Height of a single line
story_offset = 0          # Current scroll offset in pixels
story_max_offset = 0      # Maximum allowed offset
story_render = None       # Function used to re-render the story view
try:
    from nyt_config import NYT_API_KEY
except Exception:
    NYT_API_KEY = "YOUR_API_KEY_HERE"

# --- Image Gallery ---
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(IMAGES_DIR, exist_ok=True)
gallery_images = []
gallery_index = 0

# --- Notes Directory ---
NOTES_DIR = os.path.join(os.path.dirname(__file__), "notes")
os.makedirs(NOTES_DIR, exist_ok=True)

# --- IRC Chat ---
IRC_SERVER = "192.168.0.81"
IRC_PORT = 6667
IRC_CHANNEL = "#pet"
IRC_NICK = "birdie"
irc_socket = None
irc_thread = None
chat_messages = []

# IRC typing state
irc_typing = False
irc_input_text = ""
IRC_KEY_LAYOUTS = None  # defined after keyboard layouts
irc_keyboard_state = 0

# --- Scrollable Message ---
message_lines = []
message_line_h = 0
message_offset = 0
message_max_offset = 0
message_render = None


def wrap_text(text, font, max_width, draw):
    """Return a list of lines wrapped to fit within max_width."""
    lines = []
    for line in text.split("\n"):
        words = line.split()
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            width = draw.textbbox((0, 0), test, font=font)[2]
            if width <= max_width:
                current = test
            else:
                if draw.textbbox((0, 0), word, font=font)[2] > max_width:
                    if current:
                        lines.append(current)
                        current = ""
                    remaining = word
                    while remaining:
                        prefix = ""
                        for i in range(len(remaining), 0, -1):
                            segment = remaining[:i]
                            seg_width = draw.textbbox(
                                (0, 0), segment + ("-" if i < len(remaining) else ""), font=font
                            )[2]
                            if seg_width <= max_width:
                                prefix = segment
                                break
                        if not prefix:
                            prefix = remaining[0]
                            i = 1
                        lines.append(prefix + ("-" if i < len(remaining) else ""))
                        remaining = remaining[i:]
                else:
                    if current:
                        lines.append(current)
                    current = word
        if current:
            lines.append(current)
    return lines


def compute_max_visible_items(font):
    """Return the number of menu items that fit on the screen with the given font."""
    dummy_img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    dummy_draw = ImageDraw.Draw(dummy_img)
    line_height = dummy_draw.textbbox((0, 0), "Ag", font=font)[3]
    available_height = DISPLAY_HEIGHT - 25  # Header height + initial offset
    return max(1, available_height // (line_height + 4))


# --- Menu System ---
class Menu:
    def __init__(self, items, font=font_medium):
        self.items = items
        self.selected_item = 0
        self.font = font
        self.current_screen = "main_menu"  # Tracks which menu/screen is active
        self.view_start = 0  # First visible item index
        # Calculate how many items actually fit on the screen for the given font
        self.max_visible_items = compute_max_visible_items(self.font)

    def draw(self):
        if self.current_screen == "font_menu":
            self.draw_font_menu()
            return

        # Create a new blank image with black background
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
        draw = ImageDraw.Draw(img)

        # Draw header
        header_text = "Mini-OS Menu"
        if self.current_screen in ("nyt_list", "nyt_headline"):
            header_text = "NYT Top Stories"
        draw.text((5, 2), header_text, font=font_large, fill=(0, 255, 255))
        draw.line([(0, 18), (DISPLAY_WIDTH, 18)], fill=(255, 255, 255)) # Separator line

        y_offset = 25
        line_height = draw.textbbox((0, 0), "Ag", font=self.font)[3]
        visible_items = self.items[self.view_start:self.view_start + self.max_visible_items]
        for idx, item in enumerate(visible_items):
            i = self.view_start + idx
            text_color = (255, 255, 255)

            if i == self.selected_item:
                text_color = (0, 255, 0)
                draw.rectangle(
                    [(2, y_offset - 2), (DISPLAY_WIDTH - 2, y_offset + line_height + 2)],
                    fill=(50, 50, 50),
                )

            draw.text((5, y_offset), item, font=self.font, fill=text_color)
            y_offset += line_height + 4  # Consistent line spacing

        thread_safe_display(img) # Send the PIL image to the display

    def draw_font_menu(self):
        """Draw font selection menu with sample text."""
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
        draw = ImageDraw.Draw(img)
        draw.text((5, 2), "Select Font", font=font_large, fill=(0, 255, 255))
        draw.line([(0, 18), (DISPLAY_WIDTH, 18)], fill=(255, 255, 255))

        y_offset = 25
        line_height = draw.textbbox((0, 0), "Ag", font=self.font)[3]
        visible_items = self.items[self.view_start:self.view_start + self.max_visible_items]
        for idx, name in enumerate(visible_items):
            i = self.view_start + idx
            sample_font = self.font
            if name in AVAILABLE_FONTS:
                try:
                    sample_font = ImageFont.truetype(
                        AVAILABLE_FONTS[name],
                        TEXT_SIZE_MAP.get(current_text_size, TEXT_SIZE_MAP["Medium"])[1],
                    )
                except IOError:
                    sample_font = self.font
            text_color = (0, 255, 0) if i == self.selected_item else (255, 255, 255)
            if i == self.selected_item:
                draw.rectangle(
                    [(2, y_offset - 2), (DISPLAY_WIDTH - 2, y_offset + line_height + 2)],
                    fill=(50, 50, 50),
                )
            if name == "Back":
                text = name
            else:
                text = f"{name}: The quick brown fox"
            draw.text((5, y_offset), text, font=sample_font, fill=text_color)
            y_offset += line_height + 4

        thread_safe_display(img)

    def navigate(self, direction):
        if direction == "up":
            self.selected_item = (self.selected_item - 1) % len(self.items)
        elif direction == "down":
            self.selected_item = (self.selected_item + 1) % len(self.items)
        # Adjust scrolling window so selected item stays visible
        if self.selected_item < self.view_start:
            self.view_start = self.selected_item
        elif self.selected_item >= self.view_start + self.max_visible_items:
            self.view_start = self.selected_item - self.max_visible_items + 1
        self.draw() # Redraw menu after navigation

    def get_selected_item(self):
        return self.items[self.selected_item]

    def display_message_screen(self, title, message, delay=3, clear_after=True):
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), title, font=font_large, fill=(255, 255, 0)) # Yellow title
        max_width = DISPLAY_WIDTH - 10
        lines = wrap_text(message, font_medium, max_width, draw)
        y = 25
        line_height = draw.textbbox((0, 0), "A", font=font_medium)[3]
        for line in lines:
            draw.text((5, y), line, font=font_medium, fill=(255, 255, 255))
            y += line_height + 2
        thread_safe_display(img)
        time.sleep(delay)
        if clear_after:
            self.clear_display()

    def clear_display(self):
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
        thread_safe_display(img)

# --- Button Event Handler ---
def button_event_handler(channel):
    current_time = time.time()
    pin_name = next((name for name, num in BUTTON_PINS.items() if num == channel), f"Unknown Pin {channel}")

    # If the menu hasn't been initialized yet, ignore events
    if menu_instance is None:
        return

    # Simple debounce to prevent multiple triggers from one physical press
    if current_time - last_event_time[pin_name] < 0.2: # 200ms debounce time
        return

    # Only react on falling edge (button press)
    if GPIO.input(channel) == GPIO.LOW:
        button_states[pin_name] = True
        # print(f"[{datetime.now().strftime('%H:%M:%S')}] {pin_name} PRESSED!") # For debugging

        # Perform action based on the pressed button
        if menu_instance.current_screen == "main_menu":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                handle_menu_selection(menu_instance.get_selected_item())
            elif pin_name == "KEY1":
                if menu_instance.selected_item != len(menu_instance.items) - 1:
                    menu_instance.selected_item = len(menu_instance.items) - 1
                    menu_instance.draw()
            elif pin_name == "KEY2":
                show_info()
                menu_instance.draw()
        elif menu_instance.current_screen == "settings":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                handle_settings_selection(menu_instance.get_selected_item())
            elif pin_name == "KEY1":
                show_main_menu()
        elif menu_instance.current_screen == "display_settings":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                handle_display_selection(menu_instance.get_selected_item())
            elif pin_name == "KEY1":
                show_settings_menu()
        elif menu_instance.current_screen == "brightness":
            global brightness_level
            if pin_name == "JOY_LEFT" and brightness_level > 0:
                brightness_level = max(0, brightness_level - 10)
                update_backlight()
                draw_brightness_screen()
            elif pin_name == "JOY_RIGHT" and brightness_level < 100:
                brightness_level = min(100, brightness_level + 10)
                update_backlight()
                draw_brightness_screen()
            elif pin_name == "JOY_PRESS" or pin_name == "KEY1":
                show_display_menu()
        elif menu_instance.current_screen == "font_menu":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                handle_font_selection(menu_instance.get_selected_item())
            elif pin_name == "KEY1":
                show_display_menu()
        elif menu_instance.current_screen == "text_size_menu":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                handle_text_size_selection(menu_instance.get_selected_item())
            elif pin_name == "KEY1":
                show_display_menu()
        elif menu_instance.current_screen == "wifi_list":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                selection = menu_instance.get_selected_item()
                if selection == "Back" or selection == "No Networks Found":
                    show_settings_menu()
                else:
                    connect_to_wifi(selection)
            elif pin_name == "KEY1":
                show_settings_menu()
        elif menu_instance.current_screen == "bluetooth_list":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                selection = menu_instance.get_selected_item()
                if selection == "Back" or selection == "No Devices Found":
                    show_settings_menu()
            elif pin_name == "KEY1":
                selection = menu_instance.get_selected_item()
                if selection == "Back" or selection == "No Devices Found":
                    show_settings_menu()
                else:
                    connect_bluetooth_device(selection)
            elif pin_name == "KEY2":
                selection = menu_instance.get_selected_item()
                if selection == "Back" or selection == "No Devices Found":
                    show_settings_menu()
                else:
                    connect_bluetooth_device_with_pin(selection)
        elif menu_instance.current_screen == "games":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                handle_games_selection(menu_instance.get_selected_item())
            elif pin_name == "KEY1":
                show_main_menu()
        elif menu_instance.current_screen == "utilities":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                handle_utilities_selection(menu_instance.get_selected_item())
            elif pin_name == "KEY1":
                show_main_menu()
        elif menu_instance.current_screen == "notes_menu":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                handle_notes_menu_selection(menu_instance.get_selected_item())
            elif pin_name == "KEY1":
                show_main_menu()
        elif menu_instance.current_screen == "notes_list":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS" and menu_instance.items[0] != "No Notes Found":
                view_note(menu_instance.get_selected_item())
            elif pin_name == "KEY3":
                show_main_menu()
        elif menu_instance.current_screen == "note_view":
            if pin_name == "JOY_UP":
                scroll_note(-1)
            elif pin_name == "JOY_DOWN":
                scroll_note(1)
            elif pin_name == "KEY1":
                if current_note_file:
                    try:
                        with open(os.path.join(NOTES_DIR, current_note_file), "r") as f:
                            text = f.read()
                    except Exception:
                        text = ""
                    start_notes(text, current_note_file)
            elif pin_name == "KEY2":
                delete_current_note()
            elif pin_name == "KEY3":
                show_notes_list()
        elif menu_instance.current_screen == "nyt_headline":
            if pin_name == "JOY_UP" and current_story_index > 0:
                draw_headline(current_story_index - 1)
            elif pin_name == "JOY_DOWN" and current_story_index < len(nyt_stories) - 1:
                draw_headline(current_story_index + 1)
            elif pin_name == "KEY1":
                draw_story_detail(current_story_index)
            elif pin_name == "KEY3":
                show_main_menu()
        elif menu_instance.current_screen == "nyt_story":
            if pin_name == "JOY_UP":
                scroll_story(-1)
            elif pin_name == "JOY_DOWN":
                scroll_story(1)
            elif pin_name == "JOY_LEFT" and current_story_index > 0:
                draw_story_detail(current_story_index - 1)
            elif pin_name == "JOY_RIGHT" and current_story_index < len(nyt_stories) - 1:
                draw_story_detail(current_story_index + 1)
            elif pin_name == "KEY1":
                open_current_story()
            elif pin_name == "KEY3":
                show_top_stories()
        elif menu_instance.current_screen == "button_game":
            if pin_name in BUTTON_NAMES:
                handle_game_input(pin_name)
        elif menu_instance.current_screen == "launch_codes":
            if pin_name in BUTTON_PINS:
                handle_launch_input(pin_name)
        elif menu_instance.current_screen == "snake":
            if pin_name in BUTTON_PINS:
                handle_snake_input(pin_name)
        elif menu_instance.current_screen == "tetris":
            if pin_name in BUTTON_PINS:
                handle_tetris_input(pin_name)
        elif menu_instance.current_screen == "rps":
            if pin_name in BUTTON_PINS:
                handle_rps_input(pin_name)
        elif menu_instance.current_screen == "space_invaders":
            if pin_name in BUTTON_PINS:
                handle_space_invaders_input(pin_name)
        elif menu_instance.current_screen == "vet_adventure":
            if pin_name in BUTTON_PINS:
                handle_vet_adventure_input(pin_name)
        elif menu_instance.current_screen == "axe":
            if pin_name in BUTTON_PINS:
                handle_axe_input(pin_name)
        elif menu_instance.current_screen == "trivia":
            if pin_name in BUTTON_PINS:
                handle_trivia_input(pin_name)
        elif menu_instance.current_screen == "notes":
            if pin_name in BUTTON_PINS:
                handle_notes_input(pin_name)
        elif menu_instance.current_screen == "image_gallery":
            if pin_name in ["JOY_LEFT", "JOY_RIGHT", "JOY_PRESS"]:
                handle_gallery_input(pin_name)
        elif menu_instance.current_screen == "scroll_message":
            if pin_name == "JOY_UP":
                scroll_message(-1)
            elif pin_name == "JOY_DOWN":
                scroll_message(1)
            elif pin_name == "KEY3":
                show_main_menu()
        elif menu_instance.current_screen == "irc_chat":
            handle_irc_chat_input(pin_name)
    else: # Button released
        button_states[pin_name] = False
        # print(f"[{datetime.now().strftime('%H:%M:%S')}] {pin_name} RELEASED.") # For debugging
    
    last_event_time[pin_name] = current_time



# Global menu instance will be created in the main block.  Defining it here
# prevents NameError in callbacks triggered before initialization.
menu_instance = None


# --- Program Launchers (Placeholders for your applications) ---

# These functions will be called when a menu item is selected.
# They should handle their own display logic using the 'device' object from luma.lcd.
# Crucially, they should manage their own execution and return control to the main menu.



def run_git_pull():
    """Update the mini_os directory using git pull."""
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    menu_instance.display_message_screen("Git Update", "Running git pull...", delay=1)
    try:
        subprocess.run(["git", "-C", repo_dir, "pull"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        menu_instance.display_message_screen("Git Update", "Pull successful", delay=2)
    except subprocess.CalledProcessError:
        menu_instance.display_message_screen("Git Update", "Pull failed", delay=2)
    menu_instance.clear_display()


def update_and_restart():
    """Update the code then restart the mini_os service."""
    run_git_pull()
    menu_instance.display_message_screen("System", "Restarting Mini-OS...", delay=2)
    subprocess.run(["sudo", "systemctl", "restart", "mini_os.service"], check=True)
    exit()


def start_image_gallery():
    """Load images from the images directory and display the first one."""
    global gallery_images, gallery_index
    stop_scrolling()
    try:
        gallery_images = [
            f for f in sorted(os.listdir(IMAGES_DIR))
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))
        ]
    except Exception:
        gallery_images = []

    if not gallery_images:
        menu_instance.display_message_screen("Gallery", "No images found", delay=3)
        show_main_menu()
        return

    gallery_index = 0
    menu_instance.current_screen = "image_gallery"
    show_gallery_image()


def show_gallery_image():
    """Display the current image in the gallery."""
    if not gallery_images:
        return
    path = os.path.join(IMAGES_DIR, gallery_images[gallery_index])
    try:
        img = Image.open(path).convert("RGB")
        img = img.resize((DISPLAY_WIDTH, DISPLAY_HEIGHT))
    except Exception:
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), "black")
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), "Load error", font=font_small, fill=(255, 0, 0))
    thread_safe_display(img)


def handle_gallery_input(pin_name):
    """Navigate through images or exit back to the main menu."""
    global gallery_index
    if pin_name == "JOY_LEFT":
        gallery_index = (gallery_index - 1) % len(gallery_images)
        show_gallery_image()
    elif pin_name == "JOY_RIGHT":
        gallery_index = (gallery_index + 1) % len(gallery_images)
        show_gallery_image()
    elif pin_name == "JOY_PRESS":
        show_main_menu()


def show_top_stories():
    """Fetch NYT top stories and show the first headline."""
    stop_scrolling()
    global nyt_stories
    try:
        resp = requests.get(
            f"https://api.nytimes.com/svc/topstories/v2/home.json?api-key={NYT_API_KEY}",
            timeout=5,
        )
        data = resp.json()
        nyt_stories = data.get("results", [])[:20]
    except Exception:
        nyt_stories = []

    if not nyt_stories:
        menu_instance.display_message_screen("NYT", "Failed to fetch stories", delay=3)
        show_main_menu()
        return

    draw_headline(0)


def draw_headline(index):
    """Display a single headline identified by index."""
    global current_story_index
    current_story_index = index
    menu_instance.current_screen = "nyt_headline"
    story = nyt_stories[index]
    title = story.get("title", "")
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
    draw = ImageDraw.Draw(img)
    max_width = DISPLAY_WIDTH - 10
    lines = wrap_text(title, font_medium, max_width, draw)
    line_h = draw.textbbox((0, 0), "A", font=font_medium)[3] + 2
    draw.text((5, 5), "NYT Top Stories", font=font_large, fill=(255, 255, 0))
    y = 25
    for line in lines:
        draw.text((5, y), line, font=font_medium, fill=(255, 255, 255))
        y += line_h
    footer = f"{index + 1}/{len(nyt_stories)} 1=Read 3=Back"
    draw.text((5, DISPLAY_HEIGHT - 10), footer, font=font_small, fill=(0, 255, 255))
    device.display(img)


def draw_story_detail(index):
    """Display selected story with manual scrolling."""
    global story_lines, story_line_h, story_offset, story_max_offset, story_render, current_story_index
    stop_scrolling()
    current_story_index = index
    menu_instance.current_screen = "nyt_story"
    story = nyt_stories[index]
    header = "NYT Story"
    text = f"{story.get('title','')}\n\n{story.get('abstract','')}"

    dummy_img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    dummy_draw = ImageDraw.Draw(dummy_img)
    max_width = DISPLAY_WIDTH - 10
    story_lines = wrap_text(text, font_small, max_width, dummy_draw)
    story_line_h = dummy_draw.textbbox((0, 0), "A", font=font_small)[3] + 2
    story_offset = 0
    available_h = DISPLAY_HEIGHT - 35
    story_max_offset = max(0, len(story_lines) * story_line_h - available_h)

    def render():
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), header, font=font_large, fill=(255, 255, 0))
        y = 25 - story_offset
        for line in story_lines:
            draw.text((5, y), line, font=font_small, fill=(255, 255, 255))
            y += story_line_h
        # Only show the back hint; opening a link isn't supported here
        draw.text((5, DISPLAY_HEIGHT - 10), "3=Back", font=font_small, fill=(0, 255, 255))
        device.display(img)

    story_render = render
    story_render()


def scroll_story(direction):
    """Scroll the currently viewed story up (-1) or down (1)."""
    global story_offset
    if not story_render:
        return
    story_offset += direction * story_line_h
    if story_offset < 0:
        story_offset = 0
    if story_offset > story_max_offset:
        story_offset = story_max_offset
    story_render()


def open_current_story():
    """Open the currently displayed story URL in a browser."""
    if not nyt_stories:
        return
    story = nyt_stories[current_story_index]
    url = story.get("url")
    if url:
        try:
            webbrowser.open(url)
        except Exception:
            pass


def show_wifi_networks():
    """Scan for Wi-Fi networks and display them in a menu."""
    stop_scrolling()

    def scan_networks():
        nets = []
        try:
            # Trigger a fresh scan then list SSIDs with NetworkManager
            subprocess.run([
                "nmcli",
                "device",
                "wifi",
                "rescan",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            output = subprocess.check_output([
                "nmcli",
                "-t",
                "-f",
                "ssid",
                "device",
                "wifi",
                "list",
            ], stderr=subprocess.DEVNULL).decode()
            nets = [line for line in output.splitlines() if line]
        except Exception:
            # Fallback to iwlist if nmcli isn't available
            try:
                output = subprocess.check_output(
                    ["iwlist", "wlan0", "scan"], stderr=subprocess.DEVNULL
                ).decode()
                nets = re.findall(r'ESSID:"([^"]+)"', output)
            except Exception:
                nets = []
        return sorted(set(nets))

    networks = scan_networks()

    if not networks:
        networks = ["No Networks Found"]

    networks.append("Back")
    menu_instance.items = networks
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "wifi_list"
    menu_instance.draw()


def show_bluetooth_devices():
    """Scan for Bluetooth devices and display them in a menu."""
    stop_scrolling()

    def scan_devices():
        devs = []
        try:
            output = subprocess.check_output(["hcitool", "scan"], stderr=subprocess.DEVNULL).decode()
            for line in output.splitlines():
                m = re.search(r"([0-9A-F:]{17})\s+(.+)", line.strip())
                if m:
                    addr, name = m.groups()
                    devs.append(f"{name} ({addr})")
        except Exception:
            devs = []
        return devs

    devices = []

    def do_scan():
        nonlocal devices
        devices = scan_devices()

    scan_thread = threading.Thread(target=do_scan)
    scan_thread.start()

    dot_cycle = ["", ".", "..", "..."]
    idx = 0
    while scan_thread.is_alive():
        msg = f"Searching for bluetooth devices{dot_cycle[idx % len(dot_cycle)]}"
        menu_instance.display_message_screen("Bluetooth", msg, delay=0.5, clear_after=False)
        idx += 1
    scan_thread.join()

    if not devices:
        devices = ["No Devices Found"]

    devices.append("Back")
    menu_instance.items = devices
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "bluetooth_list"
    menu_instance.draw()


def connect_bluetooth_device(device):
    """Attempt to connect to the selected Bluetooth device using bluetoothctl."""
    m = re.search(r"\(([0-9A-F:]{17})\)$", device)
    if not m:
        menu_instance.display_message_screen("Bluetooth", "Invalid device", delay=2)
        return
    addr = m.group(1)
    try:
        subprocess.run(["bluetoothctl", "connect", addr], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        menu_instance.display_message_screen("Bluetooth", f"Connected to {device}", delay=3)
    except subprocess.CalledProcessError as e:
        stdout = e.stdout.decode().strip() if e.stdout else ""
        stderr = e.stderr.decode().strip() if e.stderr else ""
        details = "\n".join(filter(None, [stdout, stderr])).strip()
        if not details:
            details = "Failed to connect. Ensure the device is in pairing mode and in range."
        else:
            details = f"Failed to connect to {device}.\n{details}"
        show_scroll_message("Bluetooth Error", details)


def connect_bluetooth_device_with_pin(device):
    """Pair and connect to a Bluetooth device, automatically confirming the PIN."""
    m = re.search(r"\(([0-9A-F:]{17})\)$", device)
    if not m:
        menu_instance.display_message_screen("Bluetooth", "Invalid device", delay=2)
        return
    addr = m.group(1)
    # Prepare a bluetoothctl command sequence that confirms the passkey
    bt_commands = f"pair {addr}\nyes\ntrust {addr}\nconnect {addr}\nquit\n"
    try:
        subprocess.run(
            ["bluetoothctl"],
            input=bt_commands,
            text=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        menu_instance.display_message_screen("Bluetooth", f"Connected to {device}", delay=3)
    except subprocess.CalledProcessError as e:
        stdout = e.stdout.decode().strip() if e.stdout else ""
        stderr = e.stderr.decode().strip() if e.stderr else ""
        details = "\n".join(filter(None, [stdout, stderr])).strip()
        if not details:
            details = "Failed to connect. Ensure the device is in pairing mode and in range."
        else:
            details = f"Failed to connect to {device}.\n{details}"
        show_scroll_message("Bluetooth Error", details)


def connect_to_wifi(ssid):
    """Attempt to connect to the given SSID using nmcli."""
    password = os.environ.get("MINI_OS_WIFI_PASSWORD")
    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        cmd.extend(["password", password])

    try:
        subprocess.run(cmd, check=True)
        menu_instance.display_message_screen("Wi-Fi", f"Connected to {ssid}", delay=3)
    except Exception:
        menu_instance.display_message_screen("Wi-Fi", f"Failed to connect to {ssid}", delay=3)

    show_wifi_networks()


def toggle_wifi():
    """Toggle the Wi-Fi radio state using nmcli."""
    try:
        status = subprocess.check_output(["nmcli", "radio", "wifi"]).decode().strip()
        new_state = "off" if status == "enabled" else "on"
        subprocess.run(
            ["nmcli", "radio", "wifi", new_state],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        menu_instance.display_message_screen("Wi-Fi", f"Wi-Fi {new_state}", delay=2)
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode().strip() if e.stderr else str(e)
        show_scroll_message("Wi-Fi Error", err or "Toggle failed")
    except Exception as e:
        show_scroll_message("Wi-Fi Error", str(e))


def show_scroll_message(title, message):
    """Display a scrollable message screen."""
    global message_lines, message_line_h, message_offset, message_max_offset, message_render
    stop_scrolling()
    menu_instance.current_screen = "scroll_message"
    dummy_img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    dummy_draw = ImageDraw.Draw(dummy_img)
    max_width = DISPLAY_WIDTH - 10
    message_lines = wrap_text(message, font_small, max_width, dummy_draw)
    message_line_h = dummy_draw.textbbox((0, 0), "A", font=font_small)[3] + 2
    message_offset = 0
    available_h = DISPLAY_HEIGHT - 35
    message_max_offset = max(0, len(message_lines) * message_line_h - available_h)

    def render():
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), title, font=font_large, fill=(255, 255, 0))
        y = 25 - message_offset
        for line in message_lines:
            draw.text((5, y), line, font=font_small, fill=(255, 255, 255))
            y += message_line_h
        draw.text((5, DISPLAY_HEIGHT - 10), "3=Back", font=font_small, fill=(0, 255, 255))
        thread_safe_display(img)

    message_render = render
    message_render()


def scroll_message(direction):
    """Scroll the current message up (-1) or down (1)."""
    global message_offset
    if not message_render:
        return
    message_offset += direction * message_line_h
    if message_offset < 0:
        message_offset = 0
    if message_offset > message_max_offset:
        message_offset = message_max_offset
    message_render()

# --- IRC Chat Functions ---

def connect_irc():
    """Connect to the IRC server and start listener thread."""
    global irc_socket, irc_thread
    try:
        irc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        irc_socket.connect((IRC_SERVER, IRC_PORT))
        irc_socket.sendall(f"NICK {IRC_NICK}\r\n".encode())
        irc_socket.sendall(f"USER {IRC_NICK} 0 * :{IRC_NICK}\r\n".encode())
        irc_socket.sendall(f"JOIN {IRC_CHANNEL}\r\n".encode())
    except Exception as e:
        err_msg = f"IRC connection failed: {e}"
        print(err_msg)
        chat_messages.append(err_msg)
        if len(chat_messages) > 100:
            chat_messages.pop(0)
        irc_socket = None
        return

    def listen():
        buffer = ""
        while True:
            try:
                data = irc_socket.recv(4096)
                if not data:
                    break
                buffer += data.decode(errors="ignore")
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    handle_irc_line(line)
            except Exception as e:
                err_msg = f"IRC listener error: {e}"
                print(err_msg)
                chat_messages.append(err_msg)
                if len(chat_messages) > 100:
                    chat_messages.pop(0)
                break

    irc_thread = threading.Thread(target=listen, daemon=True)
    irc_thread.start()


def handle_irc_line(line):
    """Process a single line received from IRC."""
    if line.startswith("PING"):
        token = line.split(":", 1)[1] if ":" in line else ""
        try:
            irc_socket.sendall(f"PONG :{token}\r\n".encode())
        except Exception as e:
            print(f"Failed to send PONG: {e}")
        return

    parts = line.split()
    if len(parts) >= 4 and parts[1] == "PRIVMSG" and parts[2] == IRC_CHANNEL:
        prefix = parts[0]
        message = line.split(" :", 1)[1] if " :" in line else ""
        nick = prefix.split("!")[0][1:] if prefix.startswith(":") else prefix
        chat_messages.append(f"{nick}> {message}")
        if len(chat_messages) > 100:
            chat_messages.pop(0)
        if menu_instance and menu_instance.current_screen == "irc_chat":
            draw_chat_screen()


def draw_chat_screen():
    """Render the chat screen."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
    draw = ImageDraw.Draw(img)

    max_width = DISPLAY_WIDTH - 10
    line_h = draw.textbbox((0, 0), "A", font=font_small)[3] + 2
    available_h = DISPLAY_HEIGHT - 15

    lines = []
    for msg in chat_messages:
        lines.extend(wrap_text(msg, font_small, max_width, draw))

    max_lines = available_h // line_h
    visible = lines[-max_lines:]

    y = 5
    for line in visible:
        draw.text((5, y), line, font=font_small, fill=(255, 255, 255))
        y += line_h

    draw.text((5, DISPLAY_HEIGHT - 10), "Press=Type 3=Back", font=font_small, fill=(0, 255, 255))
    thread_safe_display(img)


def draw_irc_input_screen():
    """Display the on-screen keyboard for IRC input."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
    draw = ImageDraw.Draw(img)

    max_width = DISPLAY_WIDTH - 10
    line_h = draw.textbbox((0, 0), "A", font=font_medium)[3] + 2
    lines = wrap_text(irc_input_text, font_medium, max_width, draw)
    kb_y = DISPLAY_HEIGHT // 2 - KEYBOARD_OFFSET
    tips_height = 10
    max_lines = (kb_y - 10) // line_h
    start = max(0, len(lines) - max_lines)
    y = 5
    for line in lines[start:]:
        draw.text((5, y), line, font=font_medium, fill=(255, 255, 255))
        y += line_h

    row_h = (DISPLAY_HEIGHT - kb_y - tips_height) // len(IRC_KEY_LAYOUT)
    key_w = DISPLAY_WIDTH // 10
    for r, row in enumerate(IRC_KEY_LAYOUT):
        if r == len(IRC_KEY_LAYOUT) - 1 and len(row) == 1:
            offset_x = 5
            this_key_w = DISPLAY_WIDTH - offset_x * 2
        else:
            offset_x = (DISPLAY_WIDTH - len(row) * key_w) // 2
            this_key_w = key_w
        for c, ch in enumerate(row):
            x = offset_x + c * this_key_w
            y = kb_y + r * row_h
            rect = (x + 1, y + 1, x + this_key_w - 2, y + row_h - 2)
            if r == typer_row and c == typer_col:
                draw.rectangle(rect, fill=(0, 255, 0))
                text_color = (0, 0, 0)
            else:
                draw.rectangle(rect, outline=(255, 255, 255))
                text_color = (255, 255, 255)
            bbox = draw.textbbox((0, 0), ch, font=font_small)
            tx = x + (this_key_w - (bbox[2] - bbox[0])) // 2
            ty = y + (row_h - (bbox[3] - bbox[1])) // 2
            draw.text((tx, ty), ch, font=font_small, fill=text_color)

    tips = "Press=Send 1=Select 2=Shift 3=Cancel"
    draw.text((5, DISPLAY_HEIGHT - tips_height + 2), tips, font=font_small, fill=(0, 255, 255))

    thread_safe_display(img)


def start_irc_input():
    """Begin typing a message for IRC."""
    global irc_typing, irc_input_text, irc_keyboard_state, IRC_KEY_LAYOUT, typer_row, typer_col
    irc_typing = True
    irc_input_text = ""
    irc_keyboard_state = 0
    IRC_KEY_LAYOUT = IRC_KEY_LAYOUTS[irc_keyboard_state]
    typer_row = 1
    typer_col = 0
    menu_instance.current_screen = "irc_chat"
    draw_irc_input_screen()


def send_irc_message(msg):
    """Send a message to the IRC channel."""
    if not msg:
        return
    try:
        if irc_socket:
            irc_socket.sendall(f"PRIVMSG {IRC_CHANNEL} :{msg}\r\n".encode())
    except Exception as e:
        chat_messages.append(f"Send failed: {e}")
    chat_messages.append(f"{IRC_NICK}> {msg}")
    if len(chat_messages) > 100:
        chat_messages.pop(0)


def handle_irc_chat_input(pin_name):
    """Handle input events for IRC chat and typing mode."""
    global irc_typing, irc_input_text, irc_keyboard_state, IRC_KEY_LAYOUT, typer_row, typer_col

    if not irc_typing:
        if pin_name == "JOY_PRESS":
            start_irc_input()
        elif pin_name == "KEY3":
            show_main_menu()
    else:
        if pin_name == "JOY_LEFT" and typer_col > 0:
            typer_col -= 1
        elif pin_name == "JOY_RIGHT" and typer_col < len(IRC_KEY_LAYOUT[typer_row]) - 1:
            typer_col += 1
        elif pin_name == "JOY_UP" and typer_row > 0:
            typer_row -= 1
            typer_col = min(typer_col, len(IRC_KEY_LAYOUT[typer_row]) - 1)
        elif pin_name == "JOY_DOWN" and typer_row < len(IRC_KEY_LAYOUT) - 1:
            typer_row += 1
            typer_col = min(typer_col, len(IRC_KEY_LAYOUT[typer_row]) - 1)
        elif pin_name == "JOY_PRESS":
            send_irc_message(irc_input_text)
            irc_typing = False
            irc_input_text = ""
            draw_chat_screen()
            return
        elif pin_name == "KEY1":
            irc_input_text += IRC_KEY_LAYOUT[typer_row][typer_col]
        elif pin_name == "KEY2":
            irc_keyboard_state = (irc_keyboard_state + 1) % len(IRC_KEY_LAYOUTS)
            IRC_KEY_LAYOUT = IRC_KEY_LAYOUTS[irc_keyboard_state]
            typer_row = min(typer_row, len(IRC_KEY_LAYOUT) - 1)
            typer_col = min(typer_col, len(IRC_KEY_LAYOUT[typer_row]) - 1)
        elif pin_name == "KEY3":
            irc_typing = False
            irc_input_text = ""
            draw_chat_screen()
            return
        draw_irc_input_screen()




def start_chat():
    """Enter the IRC chat view."""
    stop_scrolling()
    if irc_socket is None:
        connect_irc()
    menu_instance.current_screen = "irc_chat"
    global irc_typing, irc_input_text
    irc_typing = False
    irc_input_text = ""
    draw_chat_screen()

def run_system_monitor(duration=10):
    """Display CPU temperature, load and memory usage for a few seconds."""
    end_time = time.time() + duration
    while time.time() < end_time:
        # CPU temperature using vcgencmd if available
        try:
            output = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
            temp = output.strip().replace("temp=", "").replace("'C", "")
        except Exception:
            temp = "N/A"

        # CPU load (1 minute average)
        try:
            load = os.getloadavg()[0]
        except Exception:
            load = 0.0

        # Current CPU frequency in MHz
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") as f:
                cpu_freq = int(f.read().strip()) / 1000  # kHz -> MHz
        except Exception:
            cpu_freq = None

        # Disk usage for root filesystem
        try:
            usage = shutil.disk_usage("/")
            disk_str = f"{usage.used // (1024**3)}/{usage.total // (1024**3)}GB"
        except Exception:
            disk_str = "N/A"

        # Memory usage from /proc/meminfo
        mem_total = 0
        mem_available = 0
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        mem_total = int(line.split()[1])
                    elif line.startswith("MemAvailable"):
                        mem_available = int(line.split()[1])
        except Exception:
            pass
        mem_used = mem_total - mem_available
        if mem_total:
            mem_str = f"{mem_used//1024}/{mem_total//1024}MB"
        else:
            mem_str = "N/A"

        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), "System Monitor", font=font_large, fill=(255, 255, 0))
        draw.text((5, 25), f"Temp: {temp}C", font=font_medium, fill=(255, 255, 255))
        draw.text((5, 40), f"Load: {load:.2f}", font=font_medium, fill=(255, 255, 255))
        if cpu_freq is not None:
            draw.text((5, 55), f"Freq: {cpu_freq:.0f}MHz", font=font_medium, fill=(255, 255, 255))
        else:
            draw.text((5, 55), "Freq: N/A", font=font_medium, fill=(255, 255, 255))
        draw.text((5, 70), f"Mem: {mem_str}", font=font_medium, fill=(255, 255, 255))
        draw.text((5, 85), f"Disk: {disk_str}", font=font_medium, fill=(255, 255, 255))
        thread_safe_display(img)
        time.sleep(1)
    menu_instance.clear_display()

def show_info():
    menu_instance.display_message_screen("System Info", "Raspberry Pi Mini-OS\nVersion 1.0\nST7735S Display", delay=4)
    menu_instance.clear_display()

def show_date_time(duration=10):
    """Display the current date and time for a few seconds."""
    end_time = time.time() + duration
    while time.time() < end_time:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), "Date & Time", font=font_large, fill=(255, 255, 0))
        max_width = DISPLAY_WIDTH - 10
        lines = wrap_text(now, font_medium, max_width, draw)
        y = 30
        line_height = draw.textbbox((0, 0), "A", font=font_medium)[3]
        for line in lines:
            draw.text((5, y), line, font=font_medium, fill=(255, 255, 255))
            y += line_height + 2
        thread_safe_display(img)
        time.sleep(1)
    menu_instance.clear_display()

def show_network_info(duration=10):
    """Display basic network information such as IP address and Wi-Fi SSID."""
    try:
        ip_output = subprocess.check_output(["hostname", "-I"]).decode().strip()
        ip_addr = ip_output if ip_output else "N/A"
    except Exception:
        ip_addr = "N/A"

    try:
        ssid_output = subprocess.check_output(["iwgetid", "-r"]).decode().strip()
        ssid = ssid_output if ssid_output else "N/A"
    except Exception:
        ssid = "N/A"

    end_time = time.time() + duration
    while time.time() < end_time:
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), "Network Info", font=font_large, fill=(255, 255, 0))
        max_width = DISPLAY_WIDTH - 10
        y = 25
        for line in wrap_text(f"IP: {ip_addr}", font_small, max_width, draw):
            draw.text((5, y), line, font=font_small, fill=(255, 255, 255))
            y += draw.textbbox((0, 0), line, font=font_small)[3] + 2
        for line in wrap_text(f"SSID: {ssid}", font_small, max_width, draw):
            draw.text((5, y), line, font=font_small, fill=(255, 255, 255))
            y += draw.textbbox((0, 0), line, font=font_small)[3] + 2
        thread_safe_display(img)
        time.sleep(1)

    menu_instance.clear_display()

def start_web_server():
    """Start the lightweight Flask web server."""
    try:
        ip_output = subprocess.check_output(["hostname", "-I"]).decode().strip()
        ip_addr = ip_output.split()[0] if ip_output else "localhost"
    except Exception:
        ip_addr = "localhost"

    try:
        from utilities import web_server
        threading.Thread(target=web_server.run, daemon=True).start()
        menu_instance.display_message_screen(
            "Web Server", f"Running on http://{ip_addr}:8000", delay=3
        )
    except Exception as e:
        menu_instance.display_message_screen(
            "Web Server", f"Failed to start: {e}", delay=3
        )

# --- Reaction Game ---

def draw_game_screen(prompt, time_left=None):
    """Display the current round prompt and countdown timer."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
    draw = ImageDraw.Draw(img)
    draw.text((5, 5), f"Round {game_round+1}", font=font_medium, fill=(255, 255, 255))
    draw.text((5, 20), f"Score: {game_score}", font=font_medium, fill=(255, 255, 255))

    if time_left is not None:
        timer_text = str(int(time_left))
        bbox = draw.textbbox((0, 0), timer_text, font=font_large)
        draw.text((DISPLAY_WIDTH - bbox[2] - 5, 5), timer_text, font=font_large, fill=(255, 0, 0))

    max_width = DISPLAY_WIDTH - 10
    y = 45
    line_height = draw.textbbox((0, 0), "A", font=font_large)[3] + 2
    for line in wrap_text(prompt, font_large, max_width, draw):
        draw.text((5, y), line, font=font_large, fill=(0, 255, 0))
        y += line_height

    thread_safe_display(img)


def stop_scrolling():
    """Placeholder for previous scrolling support (no-op)."""
    pass


def start_timer():
    """Start the countdown timer for the reaction game."""
    global timer_thread
    stop_timer()

    def timer_task():
        global timer_thread
        while not timer_stop_event.is_set():
            remaining = timer_end_time - time.time()
            if remaining <= 0:
                break
            draw_game_screen(f"Press {BUTTON_NAMES[game_prompt]}", remaining)
            time.sleep(0.1)

        if not timer_stop_event.is_set():
            menu_instance.display_message_screen("Time's Up!", f"Score: {game_score}", delay=2)
            show_main_menu()
        timer_thread = None

    timer_stop_event.clear()
    timer_thread = threading.Thread(target=timer_task, daemon=True)
    timer_thread.start()


def stop_timer():
    """Stop the reaction game timer thread."""
    global timer_thread
    if timer_thread:
        timer_stop_event.set()
        timer_thread.join()
        timer_thread = None


def start_button_game():
    """Begin the button reaction game."""
    global game_round, game_score
    stop_scrolling()
    stop_timer()
    game_round = 0
    game_score = 0
    menu_instance.current_screen = "button_game"
    next_game_round()


def next_game_round():
    """Select a new button and start the countdown timer."""
    global game_prompt, timer_end_time
    actions = list(BUTTON_NAMES.keys())
    game_prompt = random.choice(actions)
    timer_end_time = time.time() + 3
    prompt_text = f"Press {BUTTON_NAMES[game_prompt]}"
    draw_game_screen(prompt_text, 3)
    start_timer()


def handle_game_input(pin_name):
    """Process button presses for the reaction game."""
    global game_round, game_score
    stop_timer()
    if pin_name == game_prompt:
        game_score += 1
        game_round += 1
        next_game_round()
    else:
        menu_instance.display_message_screen("Wrong Button!", f"Score: {game_score}", delay=2)
        show_main_menu()

# --- Launch Codes Game ---

launch_round = 0
launch_sequence = ""
launch_input = ""
TOTAL_LAUNCH_ROUNDS = 5


def generate_launch_sequence():
    """Generate a new code sequence based on the current round."""
    global launch_sequence, launch_input
    length = launch_round + 2
    launch_sequence = "".join(str(random.randint(1, 3)) for _ in range(length))
    launch_input = ""


def draw_launch_code(show_sequence=False):
    """Display either the code to memorize or the input prompt."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
    draw = ImageDraw.Draw(img)
    draw.text(
        (5, 5),
        f"Round {launch_round}/{TOTAL_LAUNCH_ROUNDS}",
        font=font_medium,
        fill=(255, 255, 255),
    )
    if show_sequence:
        draw.text((5, 30), "Code:", font=font_large, fill=(255, 255, 0))
        draw.text((5, 55), " ".join(launch_sequence), font=font_large, fill=(0, 255, 0))
    else:
        draw.text((5, 30), "Enter:", font=font_large, fill=(255, 255, 0))
        draw.text((5, 55), launch_input, font=font_large, fill=(0, 255, 0))
        draw.text((5, 90), "Up=Submit Down=Clear", font=font_small, fill=(255, 255, 255))
    thread_safe_display(img)


def start_launch_codes(rounds=5):
    """Initialize the Launch Codes game."""
    global launch_round, TOTAL_LAUNCH_ROUNDS
    stop_scrolling()
    launch_round = 1
    TOTAL_LAUNCH_ROUNDS = rounds
    menu_instance.current_screen = "launch_codes"
    generate_launch_sequence()
    draw_launch_code(show_sequence=True)
    time.sleep(2)
    draw_launch_code()


def handle_launch_input(pin_name):
    """Process button and joystick input for the Launch Codes game."""
    global launch_round, launch_input
    if pin_name == "KEY1":
        launch_input += "1"
    elif pin_name == "KEY2":
        launch_input += "2"
    elif pin_name == "KEY3":
        launch_input += "3"
    elif pin_name == "JOY_DOWN":
        launch_input = ""
    elif pin_name == "JOY_LEFT":
        draw_launch_code(show_sequence=True)
        time.sleep(2)
    elif pin_name == "JOY_UP":
        if launch_input == launch_sequence:
            if launch_round >= TOTAL_LAUNCH_ROUNDS:
                menu_instance.display_message_screen("Success", "Bomb Defused!", delay=3)
                show_main_menu()
                return
            launch_round += 1
            generate_launch_sequence()
            draw_launch_code(show_sequence=True)
            time.sleep(2)
            draw_launch_code()
            return
        else:
            menu_instance.display_message_screen("Failure", "Wrong Code", delay=3)
            show_main_menu()
            return
    draw_launch_code()

# --- Additional Games ---

def start_snake():
    stop_scrolling()
    snake.init(thread_safe_display, (font_small, font_medium, font_large), show_main_menu)
    menu_instance.current_screen = "snake"
    snake.start()


def handle_snake_input(pin_name):
    snake.handle_input(pin_name)


def start_tetris():
    stop_scrolling()
    tetris.init(thread_safe_display, (font_small, font_medium, font_large), show_main_menu)
    menu_instance.current_screen = "tetris"
    tetris.start()


def handle_tetris_input(pin_name):
    tetris.handle_input(pin_name)


def start_rps():
    stop_scrolling()
    rps.init(thread_safe_display, (font_small, font_medium, font_large), show_main_menu)
    menu_instance.current_screen = "rps"
    rps.start()


def handle_rps_input(pin_name):
    rps.handle_input(pin_name)


def start_space_invaders():
    stop_scrolling()
    space_invaders.init(
        thread_safe_display, (font_small, font_medium, font_large), show_main_menu
    )
    menu_instance.current_screen = "space_invaders"
    space_invaders.start()


def handle_space_invaders_input(pin_name):
    space_invaders.handle_input(pin_name)

# --- Veterinary Adventure ---

def start_vet_adventure():
    stop_scrolling()
    vet_adventure.init(
        thread_safe_display, (font_small, font_medium, font_large), show_main_menu
    )
    menu_instance.current_screen = "vet_adventure"
    vet_adventure.start()


def handle_vet_adventure_input(pin_name):
    vet_adventure.handle_input(pin_name)

# --- Axe Game ---

def start_axe():
    stop_scrolling()
    axe.init(thread_safe_display, (font_small, font_medium, font_large), show_main_menu)
    menu_instance.current_screen = "axe"
    axe.start()


def handle_axe_input(pin_name):
    axe.handle_input(pin_name)

# --- Trivia Game ---

def start_trivia():
    stop_scrolling()
    trivia.init(thread_safe_display, (font_small, font_medium, font_large), show_main_menu)
    menu_instance.current_screen = "trivia"
    trivia.start()


def handle_trivia_input(pin_name):
    trivia.handle_input(pin_name)

# --- Notes Program ---

notes_text = ""
typer_row = 1  # Start with the A row
typer_col = 0  # Column for A
keyboard_state = 0  # 0=upper,1=lower,2=punct
# Automatically switch to lowercase after the first typed letter
notes_auto_lower = False

KEYBOARD_UPPER = [
    list("QWERTYUIOP"),
    list("ASDFGHJKL"),
    list("ZXCVBNM"),
    [" "]  # Space bar
]

KEYBOARD_LOWER = [
    list("qwertyuiop"),
    list("asdfghjkl"),
    list("zxcvbnm"),
    [" "]
]

KEYBOARD_PUNCT = [
    list("!@#$%^&*()"),
    list("-_=+[]{}"),
    list(";:'\",.<>/?"),
    [" "]
]

KEY_LAYOUTS = [KEYBOARD_UPPER, KEYBOARD_LOWER, KEYBOARD_PUNCT]
KEY_LAYOUT = KEY_LAYOUTS[keyboard_state]

# IRC keyboard uses lower case by default
IRC_KEY_LAYOUTS = [KEYBOARD_LOWER, KEYBOARD_UPPER, KEYBOARD_PUNCT]
IRC_KEY_LAYOUT = IRC_KEY_LAYOUTS[irc_keyboard_state]

# Note viewing state
notes_files = []
current_note_index = 0
note_lines = []
note_line_h = 0
note_offset = 0
note_max_offset = 0
note_render = None
current_note_file = None  # filename of the note being viewed
editing_note_filename = None  # filename when editing an existing note


def draw_notes_screen():
    """Render the current text and onscreen keyboard."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
    draw = ImageDraw.Draw(img)

    # Draw typed text in the top half
    max_width = DISPLAY_WIDTH - 10
    line_h = draw.textbbox((0, 0), "A", font=font_medium)[3] + 2
    lines = wrap_text(notes_text, font_medium, max_width, draw)
    kb_y = DISPLAY_HEIGHT // 2 - KEYBOARD_OFFSET
    tips_height = 10  # Space at bottom for key tips
    max_lines = (kb_y - 10) // line_h
    start = max(0, len(lines) - max_lines)
    y = 5
    for line in lines[start:]:
        draw.text((5, y), line, font=font_medium, fill=(255, 255, 255))
        y += line_h

    # Keyboard layout in bottom half
    row_h = (DISPLAY_HEIGHT - kb_y - tips_height) // len(KEY_LAYOUT)
    key_w = DISPLAY_WIDTH // 10
    for r, row in enumerate(KEY_LAYOUT):
        if r == len(KEY_LAYOUT) - 1 and len(row) == 1:
            offset_x = 5
            this_key_w = DISPLAY_WIDTH - offset_x * 2
        else:
            offset_x = (DISPLAY_WIDTH - len(row) * key_w) // 2
            this_key_w = key_w
        for c, ch in enumerate(row):
            x = offset_x + c * this_key_w
            y = kb_y + r * row_h
            rect = (x + 1, y + 1, x + this_key_w - 2, y + row_h - 2)
            if r == typer_row and c == typer_col:
                draw.rectangle(rect, fill=(0, 255, 0))
                text_color = (0, 0, 0)
            else:
                draw.rectangle(rect, outline=(255, 255, 255))
                text_color = (255, 255, 255)
            bbox = draw.textbbox((0, 0), ch, font=font_small)
            tx = x + (this_key_w - (bbox[2] - bbox[0])) // 2
            ty = y + (row_h - (bbox[3] - bbox[1])) // 2
            draw.text((tx, ty), ch, font=font_small, fill=text_color)

    tips_text = "1=Shift 2=Delete 3=Save"
    draw.text((5, DISPLAY_HEIGHT - tips_height + 2), tips_text,
              font=font_small, fill=(0, 255, 255))

    thread_safe_display(img)


def start_notes(text="", filename=None):
    """Initialize the Notes program. Optionally preload text for editing."""
    global notes_text, typer_row, typer_col, keyboard_state, KEY_LAYOUT, notes_auto_lower, editing_note_filename
    stop_scrolling()
    notes_text = text
    editing_note_filename = filename
    typer_row = 1
    typer_col = 0
    keyboard_state = 0
    KEY_LAYOUT = KEY_LAYOUTS[keyboard_state]
    # Enable auto switch to lowercase after the first typed letter
    notes_auto_lower = True
    menu_instance.current_screen = "notes"
    draw_notes_screen()


def handle_notes_input(pin_name):
    """Handle joystick and button input for Notes."""
    global typer_row, typer_col, notes_text, keyboard_state, KEY_LAYOUT, notes_auto_lower, editing_note_filename
    if pin_name == "JOY_LEFT" and typer_col > 0:
        typer_col -= 1
    elif pin_name == "JOY_RIGHT" and typer_col < len(KEY_LAYOUT[typer_row]) - 1:
        typer_col += 1
    elif pin_name == "JOY_UP" and typer_row > 0:
        typer_row -= 1
        typer_col = min(typer_col, len(KEY_LAYOUT[typer_row]) - 1)
    elif pin_name == "JOY_DOWN" and typer_row < len(KEY_LAYOUT) - 1:
        typer_row += 1
        typer_col = min(typer_col, len(KEY_LAYOUT[typer_row]) - 1)
    elif pin_name == "JOY_PRESS":
        ch = KEY_LAYOUT[typer_row][typer_col]
        notes_text += ch
        # After the first typed letter in uppercase, switch to lowercase
        if notes_auto_lower and keyboard_state == 0 and ch.isalpha():
            keyboard_state = 1
            KEY_LAYOUT = KEY_LAYOUTS[keyboard_state]
            typer_row = min(typer_row, len(KEY_LAYOUT) - 1)
            typer_col = min(typer_col, len(KEY_LAYOUT[typer_row]) - 1)
            notes_auto_lower = False
    elif pin_name == "KEY1":
        keyboard_state = (keyboard_state + 1) % len(KEY_LAYOUTS)
        KEY_LAYOUT = KEY_LAYOUTS[keyboard_state]
        typer_row = min(typer_row, len(KEY_LAYOUT) - 1)
        typer_col = min(typer_col, len(KEY_LAYOUT[typer_row]) - 1)
    elif pin_name == "KEY2":
        notes_text = notes_text[:-1]
    elif pin_name == "KEY3":
        save_note(notes_text, editing_note_filename)
        editing_note_filename = None
        show_main_menu()
        return
    draw_notes_screen()


def save_note(text, filename=None):
    """Save the given text to a file. If filename is None create a new note."""
    if not text:
        return
    if filename:
        path = os.path.join(NOTES_DIR, filename)
    else:
        pattern = re.compile(r"note(\d+)\.txt")
        existing = [int(m.group(1)) for m in (pattern.match(f) for f in os.listdir(NOTES_DIR)) if m]
        next_num = max(existing, default=0) + 1
        path = os.path.join(NOTES_DIR, f"note{next_num}.txt")
    with open(path, "w") as f:
        f.write(text)


def show_notes_list():
    """Display a menu of saved notes."""
    stop_scrolling()
    global notes_files, current_note_file
    current_note_file = None
    try:
        notes_files = sorted(
            f for f in os.listdir(NOTES_DIR) if f.lower().endswith(".txt")
        )
    except Exception:
        notes_files = []

    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    if notes_files:
        menu_instance.items = notes_files
    else:
        menu_instance.items = ["No Notes Found"]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "notes_list"
    menu_instance.draw()


def view_note(filename):
    """Show the contents of a single note with scrolling."""
    global note_lines, note_line_h, note_offset, note_max_offset, note_render, current_note_file
    stop_scrolling()
    menu_instance.current_screen = "note_view"
    current_note_file = filename
    path = os.path.join(NOTES_DIR, filename)
    try:
        with open(path, "r") as f:
            text = f.read()
    except Exception:
        text = "Error reading file"

    dummy_img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    dummy_draw = ImageDraw.Draw(dummy_img)
    max_width = DISPLAY_WIDTH - 10
    note_lines = wrap_text(text, font_small, max_width, dummy_draw)
    note_line_h = dummy_draw.textbbox((0, 0), "A", font=font_small)[3] + 2
    note_offset = 0
    available_h = DISPLAY_HEIGHT - 35
    note_max_offset = max(0, len(note_lines) * note_line_h - available_h)

    def render():
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), filename, font=font_large, fill=(255, 255, 0))
        y = 25 - note_offset
        for line in note_lines:
            draw.text((5, y), line, font=font_small, fill=(255, 255, 255))
            y += note_line_h
        draw.text((5, DISPLAY_HEIGHT - 10), "1=Edit 2=Delete 3=Back", font=font_small, fill=(0, 255, 255))
        thread_safe_display(img)

    note_render = render
    note_render()


def scroll_note(direction):
    global note_offset
    if not note_render:
        return
    note_offset += direction * note_line_h
    if note_offset < 0:
        note_offset = 0
    if note_offset > note_max_offset:
        note_offset = note_max_offset
    note_render()


def delete_current_note():
    """Delete the note currently being viewed and return to the list."""
    global current_note_file
    if not current_note_file:
        return
    try:
        os.remove(os.path.join(NOTES_DIR, current_note_file))
    except Exception:
        pass
    current_note_file = None
    show_notes_list()

def update_backlight():
    if backlight_pwm:
        backlight_pwm.ChangeDutyCycle(brightness_level)


def draw_brightness_screen():
    img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
    draw = ImageDraw.Draw(img)
    draw.text((5, 5), "Brightness", font=font_large, fill=(255, 255, 0))
    bar_width = int((DISPLAY_WIDTH - 10) * brightness_level / 100)
    draw.rectangle([(5, 30), (5 + bar_width, 50)], fill=(0, 255, 0))
    draw.rectangle([(5, 30), (DISPLAY_WIDTH - 5, 50)], outline=(255, 255, 255))
    draw.text((5, 55), f"{brightness_level}%", font=font_medium, fill=(255, 255, 255))
    thread_safe_display(img)


def show_settings_menu():
    """Top-level settings menu."""
    stop_scrolling()
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.items = [
        "Display",
        "Wi-Fi Setup",
        "Bluetooth",
        "Toggle Wi-Fi",
        "Shutdown",
        "Reboot",
        "Back",
    ]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "settings"
    menu_instance.draw()


def show_display_menu():
    """Display settings submenu."""
    stop_scrolling()
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.items = ["Brightness", "Font", "Text Size", "Back"]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "display_settings"
    menu_instance.draw()


def show_font_menu():
    """List available fonts with a sample line."""
    stop_scrolling()
    menu_instance.items = list(AVAILABLE_FONTS.keys()) + ["Back"]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.current_screen = "font_menu"
    menu_instance.draw()


def show_text_size_menu():
    """Allow the user to select the text size."""
    stop_scrolling()
    menu_instance.items = list(TEXT_SIZE_MAP.keys()) + ["Back"]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.current_screen = "text_size_menu"
    menu_instance.draw()


def handle_display_selection(selection):
    if selection == "Brightness":
        menu_instance.current_screen = "brightness"
        draw_brightness_screen()
    elif selection == "Font":
        show_font_menu()
    elif selection == "Text Size":
        show_text_size_menu()
    elif selection == "Back":
        show_settings_menu()


def handle_font_selection(selection):
    global current_font_name
    if selection == "Back":
        show_display_menu()
        return
    current_font_name = selection
    update_fonts()
    menu_instance.font = font_medium
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.display_message_screen("Font", f"{selection} selected", delay=2)
    show_display_menu()


def handle_text_size_selection(selection):
    global current_text_size
    if selection == "Back":
        show_display_menu()
        return
    current_text_size = selection
    update_fonts()
    menu_instance.font = font_medium
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.display_message_screen("Text Size", f"{selection} selected", delay=2)
    show_display_menu()


def show_games_menu():
    stop_scrolling()
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.items = [
        "Button Game",
        "Launch Codes",
        "Snake",
        "Tetris",
        "Rock Paper Scissors",
        "Space Invaders",
        "Vet Adventure",
        "Axe",
        "Trivia",
        "Back",
    ]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "games"
    menu_instance.draw()


def handle_games_selection(selection):
    if selection == "Button Game":
        start_button_game()
        return
    elif selection == "Launch Codes":
        start_launch_codes()
        return
    elif selection == "Snake":
        start_snake()
        return
    elif selection == "Tetris":
        start_tetris()
        return
    elif selection == "Rock Paper Scissors":
        start_rps()
        return
    elif selection == "Space Invaders":
        start_space_invaders()
        return
    elif selection == "Vet Adventure":
        start_vet_adventure()
        return
    elif selection == "Axe":
        start_axe()
        return
    elif selection == "Trivia":
        start_trivia()
        return
    elif selection == "Back":
        show_main_menu()


def show_notes_menu():
    """Submenu for Notes with write/read options."""
    stop_scrolling()
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.items = ["Write Note", "Read Note"]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "notes_menu"
    menu_instance.draw()


def handle_notes_menu_selection(selection):
    if selection == "Write Note":
        start_notes()
        return
    elif selection == "Read Note":
        show_notes_list()
        return
    show_main_menu()


def show_utilities_menu():
    """Submenu containing system utilities."""
    stop_scrolling()
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.items = [
        "System Monitor",
        "Network Info",
        "Date & Time",
        "Show Info",
        "Web Server",
        "Back",
    ]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "utilities"
    menu_instance.draw()


def handle_utilities_selection(selection):
    if selection == "System Monitor":
        run_system_monitor()
    elif selection == "Network Info":
        show_network_info()
    elif selection == "Date & Time":
        show_date_time()
    elif selection == "Show Info":
        show_info()
    elif selection == "Web Server":
        start_web_server()
    elif selection == "Back":
        show_main_menu()


def show_main_menu():
    stop_scrolling()
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.items = [
        "Update and Restart",
        "Games",
        "Notes",
        "Chat",
        "Image Gallery",
        "Utilities",
        "Top Stories",
        "Settings",
    ]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "main_menu"
    menu_instance.draw()


def handle_settings_selection(selection):
    if selection == "Display":
        show_display_menu()
    elif selection == "Wi-Fi Setup":
        show_wifi_networks()
    elif selection == "Bluetooth":
        show_bluetooth_devices()
    elif selection == "Toggle Wi-Fi":
        toggle_wifi()
    elif selection == "Shutdown":
        menu_instance.display_message_screen("System", "Shutting down...", delay=2)
        print("Shutting down now via systemctl poweroff.")
        subprocess.run(["sudo", "poweroff"], check=True)
        exit()
    elif selection == "Reboot":
        menu_instance.display_message_screen("System", "Rebooting...", delay=2)
        print("Rebooting now via systemctl reboot.")
        subprocess.run(["sudo", "reboot"], check=True)
        exit()
    elif selection == "Back":
        show_main_menu()

def handle_menu_selection(selection):
    print(f"Selected: {selection}") # This output goes to journalctl
    if selection == "Update and Restart":
        update_and_restart()
    elif selection == "Games":
        show_games_menu()
    elif selection == "Notes":
        show_notes_menu()
        return
    elif selection == "Chat":
        start_chat()
        return
    elif selection == "Image Gallery":
        start_image_gallery()
        return
    elif selection == "Utilities":
        show_utilities_menu()
    elif selection == "Top Stories":
        show_top_stories()
        return
    elif selection == "Settings":
        show_settings_menu()
    
    # After any program finishes, redraw the menu
    menu_instance.draw()

# --- Main Execution ---
if __name__ == "__main__":
    menu_instance = Menu([])
    connect_irc()
    show_main_menu()

    # Attach event detection to all desired pins after the menu is ready
    for pin_name, pin_num in BUTTON_PINS.items():
        # Detect both rising and falling edges to track press/release for robustness
        GPIO.add_event_detect(pin_num, GPIO.BOTH, callback=button_event_handler, bouncetime=100)
        # bouncetime in ms helps filter out noise.

    try:
        # Initialize backlight PWM for brightness control
        GPIO.setup(BL_PIN, GPIO.OUT)
        backlight_pwm = GPIO.PWM(BL_PIN, 1000)
        backlight_pwm.start(brightness_level)

        menu_instance.draw() # Initial draw of the menu

        print("Mini-OS running. Awaiting input...")

        # Keep the script running, main logic is now handled by button_event_handler callbacks
        while True:
            time.sleep(1) # Sleep to reduce CPU usage. Callbacks wake it up.

    except KeyboardInterrupt:
        print("Mini-OS interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # Attempt to display an error message on screen
        try:
            menu_instance.display_message_screen("CRITICAL ERROR", f"See logs: {e}", delay=5)
        except Exception as display_e:
            print(f"Could not display error on screen: {display_e}")
    finally:
        print("Cleaning up display and GPIO resources...")
        try:
            menu_instance.clear_display()
            if backlight_pwm:
                backlight_pwm.stop()
            GPIO.output(BL_PIN, GPIO.LOW)
            device.cleanup() # Releases luma.lcd resources
        except Exception as cleanup_e:
            print(f"Error during cleanup: {cleanup_e}")
        GPIO.cleanup() # Always clean up GPIO 
        print("Mini-OS Exited.")
