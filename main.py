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
import select
import webbrowser
import shutil
import socket
import json
import pexpect
from games import (
    snake,
    tetris,
    rps,
    space_invaders,
    vet_adventure,
    axe,
    trivia,
    two_player_trivia,
    hack_in,
    pico_wow,
    gta_1997,
    doctor_mode,
)

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
last_event_time = {name: 0.0 for name in BUTTON_PINS.keys()}  # For basic debounce
press_start_time = {name: 0.0 for name in BUTTON_PINS.keys()}

# Friendly names for buttons/joystick used in the reaction game
BUTTON_NAMES = {
    "JOY_UP": "Joystick Up",
    "JOY_DOWN": "Joystick Down",
    "JOY_LEFT": "Joystick Left",
    "JOY_RIGHT": "Joystick Right",
    "JOY_PRESS": "Joystick Press",
    # KEY1 reserved for exiting the reaction game
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

# Blinking cursor support for the shell/console
cursor_thread = None
cursor_stop_event = threading.Event()
cursor_visible = True

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

font_small = None
font_medium = None
font_large = None
font_tiny = None

current_font_name = "DejaVu Sans"
current_text_size = "Medium"
TINY_FONT_SIZE = 6


def update_fonts():
    """Reload fonts based on the selected font and size."""
    global font_small, font_medium, font_large, font_tiny
    sizes = TEXT_SIZE_MAP.get(current_text_size, TEXT_SIZE_MAP["Medium"])
    font_path = AVAILABLE_FONTS.get(current_font_name, list(AVAILABLE_FONTS.values())[0])
    try:
        font_small = ImageFont.truetype(font_path, sizes[0])
        font_medium = ImageFont.truetype(font_path, sizes[1])
        font_large = ImageFont.truetype(font_path, sizes[2])
        font_tiny = ImageFont.truetype(font_path, TINY_FONT_SIZE)
    except IOError:
        print("Defaulting to built-in fonts.")
        font_small = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_tiny = ImageFont.load_default()


update_fonts()

# --- Color Schemes ---
# Basic menu color palettes inspired by macOS Terminal themes.
COLOR_SCHEMES = {
    "Default": {
        "background": "black",
        "text": (255, 255, 255),
        "header": (0, 255, 255),
        "highlight_bg": (50, 50, 50),
        "highlight_text": (0, 255, 0),
        "title": (255, 255, 0),
    },
    "Homebrew": {
        "background": (0, 0, 0),
        "text": (0, 255, 0),
        "header": (255, 165, 0),
        "highlight_bg": (40, 40, 40),
        "highlight_text": (255, 255, 255),
        "title": (255, 165, 0),
    },
    "Pro": {
        "background": (0, 0, 0),
        "text": (194, 194, 194),
        "header": (255, 255, 255),
        "highlight_bg": (64, 64, 64),
        "highlight_text": (0, 255, 255),
        "title": (255, 255, 255),
    },
    "Terminal Basic": {
        "background": (255, 255, 255),
        "text": (0, 0, 0),
        "header": (0, 0, 0),
        "highlight_bg": (164, 201, 255),
        "highlight_text": (0, 0, 0),
        "title": (0, 0, 0),
    },
    "Grass": {
        "background": (19, 119, 61),
        "text": (255, 240, 165),
        "header": (255, 176, 59),
        "highlight_bg": (182, 73, 38),
        "highlight_text": (255, 255, 255),
        "title": (255, 176, 59),
    },
    "Man Page": {
        "background": (254, 244, 156),
        "text": (0, 0, 0),
        "header": (0, 0, 0),
        "highlight_bg": (164, 201, 205),
        "highlight_text": (0, 0, 0),
        "title": (0, 0, 0),
    },
    "Novel": {
        "background": (223, 219, 195),
        "text": (59, 35, 34),
        "header": (142, 42, 25),
        "highlight_bg": (164, 163, 144),
        "highlight_text": (0, 0, 0),
        "title": (142, 42, 25),
    },
    "Ocean": {
        "background": (34, 79, 188),
        "text": (255, 255, 255),
        "header": (255, 255, 255),
        "highlight_bg": (33, 109, 255),
        "highlight_text": (255, 255, 255),
        "title": (255, 255, 255),
    },
    "Red Sands": {
        "background": (122, 37, 30),
        "text": (215, 201, 167),
        "header": (223, 189, 34),
        "highlight_bg": (164, 163, 144),
        "highlight_text": (0, 0, 0),
        "title": (223, 189, 34),
    },
    "Espresso": {
        "background": (50, 50, 50),
        "text": (255, 255, 255),
        "header": (255, 255, 255),
        "highlight_bg": (91, 91, 91),
        "highlight_text": (255, 255, 255),
        "title": (255, 255, 255),
    },
}

current_color_scheme = COLOR_SCHEMES["Default"]
current_color_scheme_name = "Default"

def apply_color_scheme(name):
    """Set the active color scheme by name."""
    global current_color_scheme, current_color_scheme_name
    if name in COLOR_SCHEMES:
        current_color_scheme = COLOR_SCHEMES[name]
        current_color_scheme_name = name
        save_settings()
        if menu_instance:
            menu_instance.draw()

# --- Wi-Fi Status ---
wifi_connected = False
_wifi_check_time = 0


def is_wifi_connected():
    """Return True if the system is connected to Wi-Fi."""
    global wifi_connected, _wifi_check_time
    if time.time() - _wifi_check_time > 5:
        _wifi_check_time = time.time()
        try:
            output = subprocess.check_output(
                ["iwgetid", "-r"], stderr=subprocess.DEVNULL
            ).decode().strip()
            wifi_connected = bool(output)
        except Exception:
            wifi_connected = False
    return wifi_connected



# --- Backlight Control ---
brightness_level = 100  # Percentage 0-100
backlight_pwm = None

# --- Weather Codes ---
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Rain showers",
    82: "Violent rain showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm w/ hail",
    99: "Thunderstorm w/ hail",
}

# --- Weather Locations ---
WEATHER_ZIPS = ["97222", "97134"]
weather_zip_index = 0
weather_cache = {}
ZIP_KEYPAD = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["0"],
]
zip_input_text = ""
zip_row = 0
zip_col = 0

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

# Configuration file for persisting settings like color scheme
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")


def save_settings():
    """Persist current settings to disk."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"color_scheme": current_color_scheme_name}, f)
    except Exception as e:
        print(f"Failed to save settings: {e}")


def load_settings():
    """Load settings from disk if available."""
    if not os.path.exists(SETTINGS_FILE):
        return
    try:
        with open(SETTINGS_FILE) as f:
            data = json.load(f)
        scheme = data.get("color_scheme")
        if scheme in COLOR_SCHEMES:
            apply_color_scheme(scheme)
    except Exception as e:
        print(f"Failed to load settings: {e}")

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

# --- Bluetooth Pairing ---
bt_pairing_proc = None
bt_pairing_result = None
bt_pairing_cancel = False

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


def compute_max_visible_items_from_lines(lines_list, font):
    """Return a safe item count given wrapped lines for each item."""
    if not lines_list:
        return compute_max_visible_items(font)
    dummy_img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    dummy_draw = ImageDraw.Draw(dummy_img)
    line_height = dummy_draw.textbbox((0, 0), "Ag", font=font)[3]
    max_lines = max(len(lines) for lines in lines_list)
    available_height = DISPLAY_HEIGHT - 25
    return max(1, available_height // (line_height * max_lines + 4))


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
        # Optional pre-wrapped item text for variable-height lists
        self.item_lines = None

    def draw(self):
        if self.current_screen == "font_menu":
            self.draw_font_menu()
            return

        # Create a new blank image using the active background color
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=current_color_scheme["background"])
        draw = ImageDraw.Draw(img)

        # Draw header
        header_text = "Mini-OS Menu"
        if self.current_screen in ("nyt_list", "nyt_headline"):
            header_text = "NYT Top Stories"
        draw.text((5, 2), header_text, font=font_large, fill=current_color_scheme["header"])
        # Draw a separator line under the header
        draw.line([(0, 18), (DISPLAY_WIDTH, 18)], fill=current_color_scheme["text"])  # Separator line

        y_offset = 25
        line_height = draw.textbbox((0, 0), "Ag", font=self.font)[3]

        if self.current_screen == "bluetooth_list" and self.item_lines:
            for i in range(self.view_start, len(self.items)):
                lines = self.item_lines[i]
                item_height = line_height * len(lines) + 4
                if y_offset + item_height - 4 > DISPLAY_HEIGHT:
                    break
                selected = i == self.selected_item
                text_color = (
                    current_color_scheme["highlight_text"] if selected else current_color_scheme["text"]
                )
                if selected:
                    draw.rectangle(
                        [(2, y_offset - 2), (DISPLAY_WIDTH - 2, y_offset + item_height - 2)],
                        fill=current_color_scheme["highlight_bg"],
                    )
                y_line = y_offset
                for line in lines:
                    draw.text((5, y_line), line, font=self.font, fill=text_color)
                    y_line += line_height
                y_offset += item_height
        else:
            visible_items = self.items[self.view_start:self.view_start + self.max_visible_items]
            for idx, item in enumerate(visible_items):
                i = self.view_start + idx
                text_color = current_color_scheme["text"]

                if i == self.selected_item:
                    text_color = current_color_scheme["highlight_text"]
                    draw.rectangle(
                        [(2, y_offset - 2), (DISPLAY_WIDTH - 2, y_offset + line_height + 2)],
                        fill=current_color_scheme["highlight_bg"],
                    )

                draw.text((5, y_offset), item, font=self.font, fill=text_color)
                y_offset += line_height + 4  # Consistent line spacing

        thread_safe_display(img) # Send the PIL image to the display

    def draw_font_menu(self):
        """Draw font selection menu with sample text."""
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=current_color_scheme["background"])
        draw = ImageDraw.Draw(img)
        draw.text((5, 2), "Select Font", font=font_large, fill=current_color_scheme["header"])
        draw.line([(0, 18), (DISPLAY_WIDTH, 18)], fill=current_color_scheme["text"])

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
            text_color = current_color_scheme["highlight_text"] if i == self.selected_item else current_color_scheme["text"]
            if i == self.selected_item:
                draw.rectangle(
                    [(2, y_offset - 2), (DISPLAY_WIDTH - 2, y_offset + line_height + 2)],
                    fill=current_color_scheme["highlight_bg"],
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
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=current_color_scheme["background"])
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), title, font=font_large, fill=current_color_scheme["title"])
        max_width = DISPLAY_WIDTH - 10
        lines = wrap_text(message, font_medium, max_width, draw)
        y = 25
        line_height = draw.textbbox((0, 0), "A", font=font_medium)[3]
        for line in lines:
            draw.text((5, y), line, font=font_medium, fill=current_color_scheme["text"])
            y += line_height + 2
        thread_safe_display(img)
        time.sleep(delay)
        if clear_after:
            self.clear_display()

    def clear_display(self):
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=current_color_scheme["background"])
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
        press_start_time[pin_name] = current_time
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
        elif menu_instance.current_screen == "color_scheme_menu":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                handle_color_scheme_selection(menu_instance.get_selected_item())
            elif pin_name == "KEY1":
                show_display_menu()
        elif menu_instance.current_screen == "console_color_scheme_menu":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                handle_console_color_scheme_selection(
                    menu_instance.get_selected_item()
                )
            elif pin_name == "KEY1":
                start_console()
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
        elif menu_instance.current_screen == "bluetooth_menu":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "JOY_PRESS":
                handle_bluetooth_menu_selection(menu_instance.get_selected_item())
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
        elif menu_instance.current_screen == "bluetooth_pairing":
            if pin_name == "KEY1":
                global bt_pairing_cancel
                bt_pairing_cancel = True
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
        elif menu_instance.current_screen == "weather":
            if pin_name in BUTTON_PINS:
                handle_weather_input(pin_name)
        elif menu_instance.current_screen == "zip_entry":
            if pin_name in BUTTON_PINS:
                handle_zip_entry_input(pin_name)
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
        elif menu_instance.current_screen == "two_player_trivia":
            if pin_name in BUTTON_PINS:
                handle_two_player_trivia_input(pin_name)
        elif menu_instance.current_screen == "hack_in":
            if pin_name in BUTTON_PINS:
                handle_hack_in_input(pin_name)
        elif menu_instance.current_screen == "pico_wow":
            if pin_name in BUTTON_PINS:
                handle_pico_wow_input(pin_name)
        elif menu_instance.current_screen == "gta_1997":
            if pin_name in BUTTON_PINS:
                handle_gta_1997_input(pin_name)
        elif menu_instance.current_screen == "doctor_mode":
            if pin_name in BUTTON_PINS:
                handle_doctor_mode_input(pin_name)
        elif menu_instance.current_screen == "notes":
            if pin_name in BUTTON_PINS:
                handle_notes_input(pin_name)
        elif menu_instance.current_screen == "novel_typer":
            if pin_name in BUTTON_PINS:
                handle_novel_typer_input(pin_name)
        elif menu_instance.current_screen == "shell":
            if pin_name in BUTTON_PINS:
                handle_shell_input(pin_name)
        elif menu_instance.current_screen == "sudo_password":
            if pin_name in BUTTON_PINS:
                handle_sudo_password_input(pin_name)
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
        elif menu_instance.current_screen == "raspi_config":
            handle_raspi_input(pin_name)
        elif menu_instance.current_screen == "irc_chat":
            handle_irc_chat_input(pin_name)
    else: # Button released
        button_states[pin_name] = False
        hold_time = current_time - press_start_time.get(pin_name, current_time)
        if menu_instance.current_screen == "shell" and pin_name == "KEY1":
            global shell_pending_char, shell_text
            if hold_time >= 1:
                shell_text = shell_text[:-1]
            elif shell_pending_char:
                shell_text += shell_pending_char
            shell_pending_char = None
            draw_shell_screen()
        elif menu_instance.current_screen == "shell" and pin_name == "KEY2":
            if hold_time >= 1:
                global shell_keyboard_visible
                shell_keyboard_visible = False
            else:
                shell_page = (shell_page + 1) % len(SHELL_GROUP_SETS)
                shell_selected_group = None
                shell_group_index = 0
            draw_shell_screen()
        elif menu_instance.current_screen == "shell" and pin_name == "KEY3":
            if hold_time >= 1:
                show_main_menu()
            else:
                if console_mode:
                    autocomplete_shell()
                else:
                    shell_enter()
        elif (
            menu_instance.current_screen == "shell"
            and console_mode
            and pin_name == "JOY_PRESS"
        ):
            if hold_time >= 1:
                show_console_color_scheme_menu()
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
        draw.text((5, DISPLAY_HEIGHT - 10), "1=Menu 3=Back", font=font_small, fill=(0, 255, 255))
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
        devs = {}
        # Attempt a bluetoothctl scan first for better compatibility
        try:
            output = subprocess.check_output(
                ["bluetoothctl", "--timeout", "5", "scan", "on"],
                stderr=subprocess.STDOUT,
            ).decode()
            output += subprocess.check_output(["bluetoothctl", "devices"]).decode()
            for line in output.splitlines():
                m = re.search(r"Device\s+([0-9A-F:]{17})\s+(.+)", line.strip())
                if m:
                    addr, name = m.groups()
                    devs[addr] = name
        except Exception:
            # Fallback to hcitool if bluetoothctl is unavailable
            try:
                output = subprocess.check_output(
                    ["hcitool", "scan"], stderr=subprocess.DEVNULL
                ).decode()
                for line in output.splitlines():
                    m = re.search(r"([0-9A-F:]{17})\s+(.+)", line.strip())
                    if m:
                        addr, name = m.groups()
                        devs[addr] = name
            except Exception:
                devs = {}
        # Display device names before their addresses for easier identification
        # Sort the list alphabetically by device name for convenience
        return [f"{name} ({addr})" for addr, name in sorted(devs.items(), key=lambda item: item[1])]

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
    menu_instance.font = font_small
    dummy_img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    dummy_draw = ImageDraw.Draw(dummy_img)
    menu_instance.item_lines = [
        wrap_text(d, menu_instance.font, DISPLAY_WIDTH - 10, dummy_draw) for d in devices
    ]
    menu_instance.max_visible_items = compute_max_visible_items_from_lines(
        menu_instance.item_lines, menu_instance.font
    )
    menu_instance.current_screen = "bluetooth_list"
    menu_instance.draw()


def connect_bluetooth_device(device):
    """Attempt to connect to the selected Bluetooth device using bluetoothctl.

    The device must already be paired or the connection will likely fail.
    Use ``connect_bluetooth_device_with_pin`` to pair and trust new devices.
    """
    m = re.search(r"\(([0-9A-F:]{17})\)$", device)
    if not m:
        menu_instance.display_message_screen("Bluetooth", "Invalid device", delay=2)
        return
    addr = m.group(1)
    bt_commands = f"connect {addr}\nquit\n"
    try:
        result = subprocess.run(
            ["bluetoothctl"],
            input=bt_commands,
            text=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output = result.stdout.strip()
        if "Connection successful" in output:
            menu_instance.display_message_screen("Bluetooth", f"Connected to {device}", delay=3)
        else:
            details = output or "Connection attempt did not return a success message."
            details = f"Failed to connect to {device}.\n{details}"
            save_bt_failure(details)
            show_scroll_message("Bluetooth Error", details)
    except subprocess.CalledProcessError as e:
        stdout = e.stdout.decode().strip() if e.stdout else ""
        stderr = e.stderr.decode().strip() if e.stderr else ""
        details = "\n".join(filter(None, [stdout, stderr])).strip()
        if not details:
            details = "Failed to connect. Ensure the device is in pairing mode and in range."
        else:
            details = f"Failed to connect to {device}.\n{details}"
        save_bt_failure(details)
        show_scroll_message("Bluetooth Error", details)


def connect_bluetooth_device_with_pin(device):
    """Pair, trust and connect to a Bluetooth device, automatically confirming the PIN."""
    m = re.search(r"\(([0-9A-F:]{17})\)$", device)
    if not m:
        menu_instance.display_message_screen("Bluetooth", "Invalid device", delay=2)
        return
    addr = m.group(1)
    # Prepare a bluetoothctl command sequence that confirms the passkey
    bt_commands = f"pair {addr}\nyes\ntrust {addr}\nconnect {addr}\nquit\n"
    try:
        result = subprocess.run(
            ["bluetoothctl"],
            input=bt_commands,
            text=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output = result.stdout.strip()
        if "Connection successful" in output:
            menu_instance.display_message_screen("Bluetooth", f"Connected to {device}", delay=3)
        else:
            details = output or "Connection attempt did not return a success message."
            details = f"Failed to connect to {device}.\n{details}"
            save_bt_failure(details)
            show_scroll_message("Bluetooth Error", details)
    except subprocess.CalledProcessError as e:
        stdout = e.stdout.decode().strip() if e.stdout else ""
        stderr = e.stderr.decode().strip() if e.stderr else ""
        details = "\n".join(filter(None, [stdout, stderr])).strip()
        if not details:
            details = "Failed to connect. Ensure the device is in pairing mode and in range."
        else:
            details = f"Failed to connect to {device}.\n{details}"
        save_bt_failure(details)
        show_scroll_message("Bluetooth Error", details)


def start_bluetooth_pairing():
    """Make the device discoverable and wait for an incoming Bluetooth connection."""
    stop_scrolling()
    global bt_pairing_proc, bt_pairing_result, bt_pairing_cancel
    bt_pairing_result = None
    bt_pairing_cancel = False

    def pair_thread():
        """Run bluetoothctl and monitor output until a connection or cancel."""
        global bt_pairing_proc, bt_pairing_result
        try:
            bt_pairing_proc = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            setup_cmds = (
                "power on\n"
                "agent NoInputNoOutput\n"
                "default-agent\n"
                "pairable on\n"
                "discoverable on\n"
            )
            bt_pairing_proc.stdin.write(setup_cmds)
            bt_pairing_proc.stdin.flush()

            last_addr = None
            while True:
                if bt_pairing_cancel:
                    break
                rlist, _, _ = select.select([bt_pairing_proc.stdout], [], [], 0.5)
                if rlist:
                    line = bt_pairing_proc.stdout.readline()
                    if not line:
                        break
                    line = line.strip()
                    m = re.search(r"([0-9A-F:]{17})", line)
                    if m:
                        last_addr = m.group(1)
                    lower = line.lower()
                    if any(x in lower for x in ["confirm passkey", "request confirmation", "authorize service"]):
                        try:
                            bt_pairing_proc.stdin.write("yes\n")
                            bt_pairing_proc.stdin.flush()
                        except Exception:
                            pass
                    if "connection successful" in lower or "pairing successful" in lower or "paired: yes" in lower:
                        if last_addr:
                            try:
                                bt_pairing_proc.stdin.write(f"trust {last_addr}\n")
                                bt_pairing_proc.stdin.flush()
                            except Exception:
                                pass
                        bt_pairing_result = True
                        break
                    elif any(word in lower for word in ["failed", "error"]):
                        bt_pairing_result = False
                        break
        except Exception:
            bt_pairing_result = False
        finally:
            if bt_pairing_proc and bt_pairing_proc.poll() is None:
                try:
                    bt_pairing_proc.stdin.write(
                        "discoverable off\npairable off\nquit\n"
                    )
                    bt_pairing_proc.stdin.flush()
                except Exception:
                    pass
                bt_pairing_proc.terminate()
            bt_pairing_proc = None

    t = threading.Thread(target=pair_thread)
    t.start()

    menu_instance.current_screen = "bluetooth_pairing"
    dot_cycle = ["", ".", "..", "..."]
    idx = 0
    while t.is_alive() and not bt_pairing_cancel:
        msg = (
            f"Waiting for connection{dot_cycle[idx % len(dot_cycle)]}\n"
            "Press KEY1 to cancel"
        )
        menu_instance.display_message_screen(
            "Bluetooth", msg, delay=0.5, clear_after=False
        )
        idx += 1
    t.join()

    if bt_pairing_cancel:
        menu_instance.display_message_screen("Bluetooth", "Pairing cancelled", delay=2)
    else:
        if bt_pairing_result:
            menu_instance.display_message_screen("Bluetooth", "Connection successful", delay=3)
        else:
            menu_instance.display_message_screen("Bluetooth", "Connection failed", delay=3)
    show_settings_menu()


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
        draw.text((5, DISPLAY_HEIGHT - 10), "1=Menu 3=Back", font=font_small, fill=(0, 255, 255))
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

def run_system_monitor():
    """Continuously display CPU temperature, load and memory usage until the user exits."""
    next_update = 0
    while True:
        if button_states.get("KEY3"):
            break
        now = time.time()
        if now >= next_update:
            next_update = now + 1
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
            draw.text((5, DISPLAY_HEIGHT - 10), "3=Back", font=font_small, fill=(0, 255, 255))
            thread_safe_display(img)
        time.sleep(0.1)
    menu_instance.clear_display()
    show_utilities_menu()

def show_info():
    menu_instance.display_message_screen("System Info", "Raspberry Pi Mini-OS\nVersion 1.0\nST7735S Display", delay=4)
    menu_instance.clear_display()

def show_date_time(duration=10):
    """Display the current date and time for a few seconds."""
    end_time = time.time() + duration
    while time.time() < end_time:
        if button_states.get("KEY3"):
            break
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
        draw.text((5, DISPLAY_HEIGHT - 10), "3=Back", font=font_small, fill=(0, 255, 255))
        thread_safe_display(img)
        time.sleep(1)
    menu_instance.clear_display()
    show_utilities_menu()


def fetch_weather_data(zip_code):
    """Fetch weather information for the given US ZIP code."""
    try:
        r = requests.get(f"https://api.zippopotam.us/us/{zip_code}", timeout=5)
        loc = r.json()
        place = loc["places"][0]
        lat = place["latitude"]
        lon = place["longitude"]
    except Exception:
        return None

    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,weathercode&daily=temperature_2m_max,temperature_2m_min"
        "&timezone=America%2FLos_Angeles"
    )
    try:
        data = requests.get(url, timeout=5).json()
    except Exception:
        return None

    current = data.get("current", {})
    temp_c = current.get("temperature_2m")
    temp = temp_c * 9 / 5 + 32 if temp_c is not None else None
    code = current.get("weathercode")
    desc = WEATHER_CODES.get(code, f"Code {code}")
    daily = data.get("daily", {})
    high = None
    low = None
    forecast = []
    if daily.get("temperature_2m_max") and daily.get("temperature_2m_min"):
        highs_c = daily["temperature_2m_max"]
        lows_c = daily["temperature_2m_min"]
        high = highs_c[0] * 9 / 5 + 32
        low = lows_c[0] * 9 / 5 + 32
        for date, hi_c, lo_c in zip(daily.get("time", []), highs_c, lows_c):
            forecast.append({
                "date": date,
                "high": hi_c * 9 / 5 + 32,
                "low": lo_c * 9 / 5 + 32,
            })
    return {
        "temp": temp,
        "desc": desc,
        "high": high,
        "low": low,
        "forecast": forecast,
    }


def draw_weather_screen():
    """Render weather for the selected ZIP code."""
    zip_code = WEATHER_ZIPS[weather_zip_index]
    data = weather_cache.get(zip_code)
    if not data:
        data = fetch_weather_data(zip_code)
        if data:
            weather_cache[zip_code] = data
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
    draw = ImageDraw.Draw(img)
    line_h = draw.textbbox((0, 0), "A", font=font_medium)[3]
    draw.text((5, 5), f"Weather {zip_code}", font=font_large, fill=(255, 255, 0))
    y = 25
    if data and data["temp"] is not None:
        draw.text((5, y), f"Temp: {data['temp']:.1f}F", font=font_medium, fill=(255, 255, 255))
    else:
        draw.text((5, y), "Temp: N/A", font=font_medium, fill=(255, 255, 255))
    y += line_h + 2
    if data:
        draw.text((5, y), data["desc"], font=font_medium, fill=(255, 255, 255))
        y += line_h + 2
        if data["high"] is not None and data["low"] is not None:
            draw.text(
                (5, y),
                f"H:{data['high']:.1f}F L:{data['low']:.1f}F",
                font=font_medium,
                fill=(255, 255, 255),
            )
            y += line_h + 2
        if data.get("forecast"):
            for fc in data["forecast"][1:3]:
                date = fc["date"][5:]
                draw.text(
                    (5, y),
                    f"{date} {fc['high']:.0f}/{fc['low']:.0f}F",
                    font=font_small,
                    fill=(255, 255, 255),
                )
                y += draw.textbbox((0, 0), "A", font=font_small)[3] + 2
    draw.text((5, DISPLAY_HEIGHT - 10), "R=Next 1=Add 3=Back", font=font_small, fill=(0, 255, 255))
    thread_safe_display(img)


def draw_zip_entry_screen():
    """Render the numeric keypad for adding a ZIP code."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
    draw = ImageDraw.Draw(img)
    draw.text((5, 5), "New ZIP", font=font_large, fill=(255, 255, 0))
    draw.text((5, 25), zip_input_text, font=font_medium, fill=(255, 255, 255))

    start_y = 45
    row_h = (DISPLAY_HEIGHT - start_y - 15) // len(ZIP_KEYPAD)
    key_w = DISPLAY_WIDTH // 3
    for r, row in enumerate(ZIP_KEYPAD):
        offset_x = (DISPLAY_WIDTH - len(row) * key_w) // 2
        for c, ch in enumerate(row):
            x = offset_x + c * key_w
            y = start_y + r * row_h
            rect = (x + 1, y + 1, x + key_w - 2, y + row_h - 2)
            if r == zip_row and c == zip_col:
                draw.rectangle(rect, fill=(0, 255, 0))
                color = (0, 0, 0)
            else:
                draw.rectangle(rect, outline=(255, 255, 255))
                color = (255, 255, 255)
            bbox = draw.textbbox((0, 0), ch, font=font_medium)
            tx = x + (key_w - (bbox[2] - bbox[0])) // 2
            ty = y + (row_h - (bbox[3] - bbox[1])) // 2
            draw.text((tx, ty), ch, font=font_medium, fill=color)

    draw.text((5, DISPLAY_HEIGHT - 10), "1=Del 2=OK 3=Cancel", font=font_small, fill=(0, 255, 255))
    thread_safe_display(img)


def start_zip_entry():
    """Begin entering a new ZIP code."""
    global zip_input_text, zip_row, zip_col
    zip_input_text = ""
    zip_row = 0
    zip_col = 0
    menu_instance.current_screen = "zip_entry"
    draw_zip_entry_screen()


def handle_zip_entry_input(pin_name):
    """Process input while entering a ZIP code."""
    global zip_row, zip_col, zip_input_text, weather_zip_index
    if pin_name == "JOY_LEFT" and zip_col > 0:
        zip_col -= 1
    elif pin_name == "JOY_RIGHT" and zip_col < len(ZIP_KEYPAD[zip_row]) - 1:
        zip_col += 1
    elif pin_name == "JOY_UP" and zip_row > 0:
        zip_row -= 1
        zip_col = min(zip_col, len(ZIP_KEYPAD[zip_row]) - 1)
    elif pin_name == "JOY_DOWN" and zip_row < len(ZIP_KEYPAD) - 1:
        zip_row += 1
        zip_col = min(zip_col, len(ZIP_KEYPAD[zip_row]) - 1)
    elif pin_name == "JOY_PRESS":
        zip_input_text += ZIP_KEYPAD[zip_row][zip_col]
    elif pin_name == "KEY1":
        zip_input_text = zip_input_text[:-1]
    elif pin_name == "KEY2":
        if zip_input_text.isdigit() and len(zip_input_text) == 5:
            WEATHER_ZIPS.append(zip_input_text)
            weather_zip_index = len(WEATHER_ZIPS) - 1
            menu_instance.current_screen = "weather"
            draw_weather_screen()
            return
    elif pin_name == "KEY3":
        menu_instance.current_screen = "weather"
        draw_weather_screen()
        return
    draw_zip_entry_screen()


def show_weather():
    """Enter the interactive weather view."""
    stop_scrolling()
    menu_instance.current_screen = "weather"
    draw_weather_screen()


def handle_weather_input(pin_name):
    """Handle joystick and button input for the weather screen."""
    global weather_zip_index
    if pin_name == "JOY_RIGHT":
        weather_zip_index = (weather_zip_index + 1) % len(WEATHER_ZIPS)
        draw_weather_screen()
    elif pin_name == "KEY1":
        start_zip_entry()
    elif pin_name == "KEY3":
        show_main_menu()

def show_network_info():
    """Display basic network information until the user exits."""
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

    next_update = 0
    while True:
        if button_states.get("KEY3"):
            break
        now = time.time()
        if now >= next_update:
            next_update = now + 1
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
            draw.text((5, DISPLAY_HEIGHT - 10), "3=Back", font=font_small, fill=(0, 255, 255))
            thread_safe_display(img)
        time.sleep(0.1)

    menu_instance.clear_display()
    show_utilities_menu()

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
        show_utilities_menu()
    except Exception as e:
        menu_instance.display_message_screen(
            "Web Server", f"Failed to start: {e}", delay=3
        )
        show_utilities_menu()

def start_mini_games():
    """Launch the web-based mini games."""
    try:
        ip_output = subprocess.check_output(["hostname", "-I"]).decode().strip()
        ip_addr = ip_output.split()[0] if ip_output else "localhost"
    except Exception:
        ip_addr = "localhost"

    try:
        from utilities import web_server
        threading.Thread(target=web_server.run, daemon=True).start()
    except Exception:
        pass

    try:
        webbrowser.open(f"http://{ip_addr}:8000/mini-games")
    except Exception:
        pass

    menu_instance.display_message_screen(
        "Mini Games", f"Open http://{ip_addr}:8000/mini-games", delay=4
    )
    show_games_menu()

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

    draw.text((5, DISPLAY_HEIGHT - 10), "1=Quit", font=font_small, fill=(0, 255, 255))
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


def start_cursor():
    """Start blinking cursor thread for the shell."""
    global cursor_thread
    stop_cursor()

    def cursor_task():
        global cursor_thread, cursor_visible
        while not cursor_stop_event.is_set():
            cursor_visible = not cursor_visible
            draw_shell_screen()
            time.sleep(0.5)

        cursor_thread = None

    cursor_stop_event.clear()
    cursor_thread = threading.Thread(target=cursor_task, daemon=True)
    cursor_thread.start()


def stop_cursor():
    """Stop the blinking cursor."""
    global cursor_thread
    if cursor_thread:
        cursor_stop_event.set()
        cursor_thread.join()
        cursor_thread = None


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
    if pin_name == "KEY1":
        show_main_menu()
        return
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
        draw.text((5, DISPLAY_HEIGHT - 10), "Press=Quit", font=font_small, fill=(0, 255, 255))
    else:
        draw.text((5, 30), "Enter:", font=font_large, fill=(255, 255, 0))
        draw.text((5, 55), launch_input, font=font_large, fill=(0, 255, 0))
        draw.text((5, 90), "Up=Submit Down=Clear", font=font_small, fill=(255, 255, 255))
        draw.text((5, DISPLAY_HEIGHT - 10), "Press=Quit", font=font_small, fill=(0, 255, 255))
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
    if pin_name == "JOY_PRESS":
        show_main_menu()
        return
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

# --- Two Player Trivia Game ---

def start_two_player_trivia():
    stop_scrolling()
    two_player_trivia.init(thread_safe_display, (font_small, font_medium, font_large), show_main_menu)
    menu_instance.current_screen = "two_player_trivia"
    two_player_trivia.start()


def handle_two_player_trivia_input(pin_name):
    two_player_trivia.handle_input(pin_name)

# --- Pico WoW Game ---

def start_pico_wow():
    stop_scrolling()
    pico_wow.init(thread_safe_display, (font_small, font_medium, font_large), show_main_menu)
    menu_instance.current_screen = "pico_wow"
    pico_wow.start()


def handle_pico_wow_input(pin_name):
    pico_wow.handle_input(pin_name)

# --- Hack In Animation ---

def start_hack_in():
    stop_scrolling()
    hack_in.init(thread_safe_display, (font_small, font_medium, font_large), show_main_menu)
    menu_instance.current_screen = "hack_in"
    hack_in.start()


def handle_hack_in_input(pin_name):
    hack_in.handle_input(pin_name)

# --- GTA 1997 Style Game ---

def start_gta_1997():
    stop_scrolling()
    gta_1997.init(thread_safe_display, (font_small, font_medium, font_large), show_main_menu)
    menu_instance.current_screen = "gta_1997"
    gta_1997.start()


def handle_gta_1997_input(pin_name):
    gta_1997.handle_input(pin_name)

# --- Doctor Mode ---

def start_doctor_mode():
    stop_scrolling()
    doctor_mode.init(thread_safe_display, (font_small, font_medium, font_large), show_main_menu)
    menu_instance.current_screen = "doctor_mode"
    doctor_mode.start()


def handle_doctor_mode_input(pin_name):
    doctor_mode.handle_input(pin_name)

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

# --- Novel Typer ---
# Groups of letters for each page. Each joystick direction selects a group and
# repeated presses cycle through the letters in that group. KEY1 toggles pages,
# KEY2 deletes the last character and KEY3 confirms the current letter or exits
# when no group is active.
NOVEL_GROUP_SETS = [
    {
        "JOY_UP": ["A", "B", "C"],
        "JOY_DOWN": ["D", "E", "F"],
        "JOY_LEFT": ["G", "H", "I"],
        "JOY_RIGHT": ["J", "K", "L"],
        "JOY_PRESS": ["M", "N", "O"],
    },
    {
        "JOY_UP": ["P", "Q", "R"],
        "JOY_DOWN": ["S", "T", "U"],
        "JOY_LEFT": ["V", "W", "X"],
        "JOY_RIGHT": ["Y", "Z", " "],
        "JOY_PRESS": [".", "?", "!"],
    },
]

# Separate layout for the shell uses lowercase letters
SHELL_GROUP_SETS = [
    {
        "JOY_UP": ["a", "b", "c"],
        "JOY_DOWN": ["d", "e", "f"],
        "JOY_LEFT": ["g", "h", "i"],
        "JOY_RIGHT": ["j", "k", "l"],
        "JOY_PRESS": ["m", "n", "o"],
    },
    {
        "JOY_UP": ["p", "q", "r"],
        "JOY_DOWN": ["s", "t", "u"],
        "JOY_LEFT": ["v", "w", "x"],
        "JOY_RIGHT": ["y", "z", " "],
        "JOY_PRESS": [".", "?", "!"],
    },
]
novel_text = ""
novel_page = 0
novel_selected_group = None
novel_group_index = 0

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


def save_bt_failure(details):
    """Save bluetooth connection error details to the notes directory."""
    pattern = re.compile(r"btfail(\d+)\.txt")
    try:
        existing = [
            int(m.group(1))
            for m in (pattern.match(f) for f in os.listdir(NOTES_DIR))
            if m
        ]
        next_num = max(existing, default=0) + 1
        path = os.path.join(NOTES_DIR, f"btfail{next_num}.txt")
        with open(path, "w") as f:
            f.write(details)
    except Exception:
        pass


def save_connect_failure(details):
    """Save incoming bluetooth connection errors to the notes directory."""
    pattern = re.compile(r"connectfail(\d+)\.txt")
    try:
        existing = [
            int(m.group(1))
            for m in (pattern.match(f) for f in os.listdir(NOTES_DIR))
            if m
        ]
        next_num = max(existing, default=0) + 1
        path = os.path.join(NOTES_DIR, f"connectfail{next_num}.txt")
        with open(path, "w") as f:
            f.write(details)
    except Exception:
        pass


def start_bt_log_monitor():
    """Watch system bluetooth logs for failed incoming connections."""
    if not shutil.which("journalctl"):
        return

    def monitor():
        proc = subprocess.Popen(
            ["journalctl", "-fu", "bluetooth", "-n", "0", "--since", "now"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        buffer = []
        for line in iter(proc.stdout.readline, ""):
            if not line:
                break
            buffer.append(line.strip())
            lower = line.lower()
            if any(word in lower for word in ["failed", "error"]):
                details = "\n".join(buffer[-20:])
                save_connect_failure(details)
                buffer = []

    t = threading.Thread(target=monitor, daemon=True)
    t.start()



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


# --- Novel Typer Program ---

def draw_novel_typer_screen():
    """Render typed text and the joystick letter groups."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
    draw = ImageDraw.Draw(img)

    max_width = DISPLAY_WIDTH - 10
    line_h = draw.textbbox((0, 0), "A", font=font_medium)[3] + 2
    lines = wrap_text(novel_text, font_medium, max_width, draw)
    kb_y = DISPLAY_HEIGHT // 2
    tips_height = 10
    max_lines = (kb_y - 10) // line_h
    start = max(0, len(lines) - max_lines)
    y = 5
    for line in lines[start:]:
        draw.text((5, y), line, font=font_medium, fill=(255, 255, 255))
        y += line_h

    group_map = NOVEL_GROUP_SETS[novel_page]
    order = ["JOY_UP", "JOY_LEFT", "JOY_PRESS", "JOY_RIGHT", "JOY_DOWN"]
    col_w = DISPLAY_WIDTH // 5
    row_h = 10
    start_y = kb_y + 2
    for idx, g in enumerate(order):
        letters = group_map[g]
        x = idx * col_w + 2
        rect = (x, start_y - 2, x + col_w - 4, DISPLAY_HEIGHT - tips_height - 2)
        if novel_selected_group == g:
            draw.rectangle(rect, outline=(0, 255, 0))
        else:
            draw.rectangle(rect, outline=(255, 255, 255))
        for j, ch in enumerate(letters):
            color = (0, 255, 0) if (novel_selected_group == g and j == novel_group_index) else (255, 255, 255)
            ty = start_y + j * row_h
            draw.text((x + 2, ty), ch, font=font_small, fill=color)

    draw.text((5, DISPLAY_HEIGHT - tips_height + 1), "1=Pg 2=Del 3=OK/Exit", font=font_small, fill=(0, 255, 255))
    draw.text((DISPLAY_WIDTH - 20, 2), f"P{novel_page+1}", font=font_small, fill=(0, 255, 255))

    thread_safe_display(img)


def start_novel_typer():
    """Initialize the novel typer."""
    global novel_text, novel_page, novel_selected_group, novel_group_index
    stop_scrolling()
    novel_text = ""
    novel_page = 0
    novel_selected_group = None
    novel_group_index = 0
    menu_instance.current_screen = "novel_typer"
    draw_novel_typer_screen()


def handle_novel_typer_input(pin_name):
    """Process input for the novel typer."""
    global novel_page, novel_selected_group, novel_group_index, novel_text
    if pin_name in ["JOY_UP", "JOY_DOWN", "JOY_LEFT", "JOY_RIGHT", "JOY_PRESS"]:
        if novel_selected_group == pin_name:
            novel_group_index = (novel_group_index + 1) % len(NOVEL_GROUP_SETS[novel_page][pin_name])
        else:
            novel_selected_group = pin_name
            novel_group_index = 0
        draw_novel_typer_screen()
    elif pin_name == "KEY1":
        novel_page = (novel_page + 1) % len(NOVEL_GROUP_SETS)
        draw_novel_typer_screen()
    elif pin_name == "KEY2":
        novel_text = novel_text[:-1]
        draw_novel_typer_screen()
    elif pin_name == "KEY3":
        if novel_selected_group:
            ch = NOVEL_GROUP_SETS[novel_page][novel_selected_group][novel_group_index]
            novel_text += ch
            novel_selected_group = None
            novel_group_index = 0
            draw_novel_typer_screen()
        else:
            show_main_menu()


# --- Shell Program ---

shell_text = ""
shell_page = 0
shell_selected_group = None
shell_group_index = 0
shell_keyboard_visible = True
shell_pending_char = None  # store KEY1 char until release


shell_proc = None
shell_lines = []
sudo_pre_output = ""
console_mode = False
console_log_path = os.path.join(os.path.dirname(__file__), "logs", "console.log")

# Variables for sudo password prompt
sudo_pending_cmd = None
sudo_pw_text = ""
sudo_pw_keyboard_state = 1
sudo_pw_row = 1
sudo_pw_col = 0


def draw_shell_screen():
    """Render the shell with history and input using the novel keyboard."""
    img = Image.new(
        "RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=current_color_scheme["background"]
    )
    draw = ImageDraw.Draw(img)

    max_width = DISPLAY_WIDTH - 10
    tips_height = 0 if console_mode else 10
    kb_y = DISPLAY_HEIGHT // 2 if shell_keyboard_visible else DISPLAY_HEIGHT - tips_height
    line_h = draw.textbbox((0, 0), "A", font=font_small)[3] + 1

    history_lines = []
    for ln in shell_lines:
        history_lines.extend(wrap_text(ln, font_small, max_width, draw))
    cursor = "_" if cursor_visible else " "
    history_lines.extend(wrap_text(f"$ {shell_text}{cursor}", font_small, max_width, draw))
    max_lines = (kb_y - 5) // line_h
    start = max(0, len(history_lines) - max_lines)
    y = 5
    for line in history_lines[start:]:
        draw.text(
            (5, y), line, font=font_small, fill=current_color_scheme["text"]
        )
        y += line_h

    if shell_keyboard_visible:
        group_map = SHELL_GROUP_SETS[shell_page]
        order = ["JOY_UP", "JOY_LEFT", "JOY_PRESS", "JOY_RIGHT", "JOY_DOWN"]
        col_w = DISPLAY_WIDTH // 5
        row_h = 10
        start_y = kb_y + 2
        for idx, g in enumerate(order):
            letters = group_map[g]
            x = idx * col_w + 2
            rect = (x, start_y - 2, x + col_w - 4, DISPLAY_HEIGHT - tips_height - 2)
            if shell_selected_group == g:
                draw.rectangle(rect, outline=(0, 255, 0))
            else:
                draw.rectangle(rect, outline=(255, 255, 255))
            for j, ch in enumerate(letters):
                color = (0, 255, 0) if (shell_selected_group == g and j == shell_group_index) else (255, 255, 255)
                ty = start_y + j * row_h
                draw.text((x + 2, ty), ch, font=font_small, fill=color)

        tips = "1S=Select 1L=Del 2S=Next 2L=Hide 3S=Run 3L=Exit"
    else:
        tips = "1=Keyboard (3L Exit)"

    if not console_mode:
        draw.text(
            (5, DISPLAY_HEIGHT - tips_height + 2),
            tips,
            font=font_small,
            fill=current_color_scheme["header"],
        )

    thread_safe_display(img)


def start_shell(show_keyboard=True):
    """Initialize the shell input program."""
    global shell_text, shell_page, shell_selected_group, shell_group_index, shell_proc, shell_keyboard_visible
    stop_scrolling()
    if shell_proc is None:
        shell_proc = pexpect.spawn("/bin/bash", encoding="utf-8", echo=False)
    shell_text = ""
    shell_page = 0
    shell_selected_group = None
    shell_group_index = 0
    shell_keyboard_visible = show_keyboard
    menu_instance.current_screen = "shell"
    draw_shell_screen()
    start_cursor()


def start_console():
    """Launch a minimalist console that logs output."""
    global console_mode
    console_mode = True
    os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)
    start_shell(show_keyboard=False)




def draw_sudo_password_screen():
    """Render the password entry screen for sudo."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
    draw = ImageDraw.Draw(img)

    max_width = DISPLAY_WIDTH - 10
    line_h = draw.textbbox((0, 0), "A", font=font_medium)[3] + 2
    stars = "*" * len(sudo_pw_text)
    lines = wrap_text(stars, font_medium, max_width, draw)
    kb_y = DISPLAY_HEIGHT // 2 - KEYBOARD_OFFSET
    tips_height = 10
    max_lines = (kb_y - 10) // line_h
    start = max(0, len(lines) - max_lines)
    y = 5
    draw.text((5, y), "sudo password:", font=font_small, fill=(255, 255, 0))
    y += line_h
    for line in lines[start:]:
        draw.text((5, y), line, font=font_medium, fill=(255, 255, 255))
        y += line_h

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
            yk = kb_y + r * row_h
            rect = (x + 1, yk + 1, x + this_key_w - 2, yk + row_h - 2)
            if r == sudo_pw_row and c == sudo_pw_col:
                draw.rectangle(rect, fill=(0, 255, 0))
                text_color = (0, 0, 0)
            else:
                draw.rectangle(rect, outline=(255, 255, 255))
                text_color = (255, 255, 255)
            bbox = draw.textbbox((0, 0), ch, font=font_small)
            tx = x + (this_key_w - (bbox[2] - bbox[0])) // 2
            ty = yk + (row_h - (bbox[3] - bbox[1])) // 2
            draw.text((tx, ty), ch, font=font_small, fill=text_color)

    tips = "1=Shift 2=Del 3=OK/Exit"
    draw.text((5, DISPLAY_HEIGHT - tips_height + 2), tips, font=font_small, fill=(0, 255, 255))

    thread_safe_display(img)


def start_sudo_password(cmd):
    """Prompt the user to enter the sudo password."""
    global sudo_pending_cmd, sudo_pw_text, sudo_pw_keyboard_state, KEY_LAYOUT, sudo_pw_row, sudo_pw_col
    stop_scrolling()
    stop_cursor()
    sudo_pending_cmd = cmd
    sudo_pw_text = ""
    sudo_pw_keyboard_state = 1
    KEY_LAYOUT = KEY_LAYOUTS[sudo_pw_keyboard_state]
    sudo_pw_row = 1
    sudo_pw_col = 0
    menu_instance.current_screen = "sudo_password"
    draw_sudo_password_screen()


def run_sudo_command(cmd, password):
    """Run a sudo command using the provided password."""
    global shell_text, sudo_pending_cmd, sudo_pre_output, shell_proc, shell_lines, shell_keyboard_visible
    if shell_proc is None:
        shell_proc = pexpect.spawn("/bin/bash", encoding="utf-8", echo=False)
    shell_proc.sendline(password)
    try:
        shell_proc.expect("__CMD_DONE__", timeout=20)
        output = sudo_pre_output + shell_proc.before
    except pexpect.exceptions.TIMEOUT:
        output = sudo_pre_output + "Command timed out"
    shell_lines.append(f"$ {sudo_pending_cmd}")
    shell_lines.extend(output.splitlines())
    shell_text = ""
    sudo_pending_cmd = None
    sudo_pre_output = ""
    menu_instance.current_screen = "shell"
    shell_keyboard_visible = False
    draw_shell_screen()
    start_cursor()


def handle_sudo_password_input(pin_name):
    """Handle input for the sudo password screen."""
    global sudo_pw_row, sudo_pw_col, sudo_pw_text, sudo_pw_keyboard_state, KEY_LAYOUT
    if pin_name == "JOY_LEFT" and sudo_pw_col > 0:
        sudo_pw_col -= 1
    elif pin_name == "JOY_RIGHT" and sudo_pw_col < len(KEY_LAYOUT[sudo_pw_row]) - 1:
        sudo_pw_col += 1
    elif pin_name == "JOY_UP" and sudo_pw_row > 0:
        sudo_pw_row -= 1
        sudo_pw_col = min(sudo_pw_col, len(KEY_LAYOUT[sudo_pw_row]) - 1)
    elif pin_name == "JOY_DOWN" and sudo_pw_row < len(KEY_LAYOUT) - 1:
        sudo_pw_row += 1
        sudo_pw_col = min(sudo_pw_col, len(KEY_LAYOUT[sudo_pw_row]) - 1)
    elif pin_name == "JOY_PRESS":
        sudo_pw_text += KEY_LAYOUT[sudo_pw_row][sudo_pw_col]
    elif pin_name == "KEY1":
        sudo_pw_keyboard_state = (sudo_pw_keyboard_state + 1) % len(KEY_LAYOUTS)
        KEY_LAYOUT = KEY_LAYOUTS[sudo_pw_keyboard_state]
        sudo_pw_row = min(sudo_pw_row, len(KEY_LAYOUT) - 1)
        sudo_pw_col = min(sudo_pw_col, len(KEY_LAYOUT[sudo_pw_row]) - 1)
    elif pin_name == "KEY2":
        sudo_pw_text = sudo_pw_text[:-1]
    elif pin_name == "KEY3":
        if sudo_pw_text:
            run_sudo_command(sudo_pending_cmd, sudo_pw_text)
        else:
            menu_instance.current_screen = "shell"
            draw_shell_screen()
            start_cursor()
        return
    draw_sudo_password_screen()


def run_shell_command(cmd):
    """Execute the given command in a persistent shell."""
    global shell_text, shell_proc, shell_lines, sudo_pending_cmd, sudo_pre_output, shell_keyboard_visible
    if not cmd.strip():
        return
    if shell_proc is None:
        shell_proc = pexpect.spawn("/bin/bash", encoding="utf-8", echo=False)
    shell_proc.sendline(f"{cmd}; echo __CMD_DONE__")
    try:
        idx = shell_proc.expect(["sudo password:", "__CMD_DONE__"], timeout=20)
        output = shell_proc.before + shell_proc.after.replace("__CMD_DONE__", "")
        if idx == 0:
            sudo_pending_cmd = cmd
            sudo_pre_output = output
            start_sudo_password(cmd)
            return
    except pexpect.exceptions.TIMEOUT:
        output = "Command timed out"
    shell_lines.append(f"$ {cmd}")
    shell_lines.extend(output.splitlines())
    if console_mode:
        with open(console_log_path, "a") as f:
            f.write(f"$ {cmd}\n{output}\n")
    shell_text = ""
    shell_keyboard_visible = False
    draw_shell_screen()


def autocomplete_shell():
    """Perform simple tab completion using bash compgen."""
    global shell_text, shell_lines
    prefix = shell_text.split()[-1] if shell_text.split() else shell_text
    try:
        output = subprocess.check_output(
            ["bash", "-ic", f"compgen -cdfa -- '{prefix}'"],
            text=True,
        )
        matches = [line for line in output.splitlines() if line]
    except Exception:
        matches = []
    if len(matches) == 1:
        shell_text += matches[0][len(prefix):]
    elif len(matches) > 1:
        shell_lines.append(" ".join(matches))
    draw_shell_screen()


def shell_enter():
    """Execute current command and reset selection."""
    global shell_selected_group, shell_group_index
    if shell_text.strip():
        run_shell_command(shell_text)
    else:
        show_main_menu()
    shell_selected_group = None
    shell_group_index = 0


def handle_shell_input(pin_name):
    """Handle joystick and button input for the shell program."""
    global shell_page, shell_selected_group, shell_group_index, shell_text, shell_keyboard_visible

    if not shell_keyboard_visible:
        if pin_name == "KEY1":
            shell_keyboard_visible = True
            draw_shell_screen()
        return

    if pin_name in ["JOY_UP", "JOY_DOWN", "JOY_LEFT", "JOY_RIGHT", "JOY_PRESS"]:
        if shell_selected_group == pin_name:
            shell_group_index = (shell_group_index + 1) % len(SHELL_GROUP_SETS[shell_page][pin_name])
        else:
            shell_selected_group = pin_name
            shell_group_index = 0
        draw_shell_screen()
    elif pin_name == "KEY1":
        global shell_pending_char
        if shell_selected_group:
            shell_pending_char = SHELL_GROUP_SETS[shell_page][shell_selected_group][shell_group_index]
            shell_selected_group = None
            shell_group_index = 0
        else:
            shell_pending_char = None
        draw_shell_screen()

# --- raspi-config ---

raspi_proc = None
raspi_lines = []
raspi_lock = threading.Lock()


def draw_raspi_screen():
    """Render output from raspi-config in a small font."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
    draw = ImageDraw.Draw(img)
    draw.text((5, 5), "raspi-config", font=font_small, fill=(255, 255, 0))
    with raspi_lock:
        lines = raspi_lines[-10:]
    y = 15
    line_h = draw.textbbox((0, 0), "A", font=font_small)[3] + 2
    for line in lines:
        draw.text((5, y), line[:20], font=font_small, fill=(255, 255, 255))
        y += line_h
    draw.text((5, DISPLAY_HEIGHT - 10), "1=Exit", font=font_small, fill=(0, 255, 255))
    thread_safe_display(img)


def start_raspi_config():
    """Launch raspi-config using pexpect."""
    global raspi_proc, raspi_lines
    stop_scrolling()
    env = os.environ.copy()
    env["LINES"] = "15"
    env["COLUMNS"] = "32"
    raspi_proc = pexpect.spawn("sudo raspi-config", env=env, encoding="utf-8")
    raspi_lines = []
    try:
        idx = raspi_proc.expect(["[Pp]assword", pexpect.TIMEOUT], timeout=1)
        if idx == 0:
            raspi_proc.terminate(force=True)
            raspi_proc = None
            menu_instance.display_message_screen("raspi-config", "sudo password required", delay=3)
            show_settings_menu()
            return
    except Exception:
        pass

    def reader():
        global raspi_proc
        while True:
            try:
                data = raspi_proc.read_nonblocking(size=1024, timeout=0.1)
            except pexpect.exceptions.TIMEOUT:
                continue
            except pexpect.exceptions.EOF:
                break
            with raspi_lock:
                for l in data.splitlines():
                    raspi_lines.append(l)
                    if len(raspi_lines) > 50:
                        raspi_lines.pop(0)
            draw_raspi_screen()

    threading.Thread(target=reader, daemon=True).start()
    menu_instance.current_screen = "raspi_config"
    draw_raspi_screen()


def handle_raspi_input(pin_name):
    """Send basic navigation keys to raspi-config."""
    global raspi_proc
    if raspi_proc is None:
        return
    if pin_name == "JOY_UP":
        raspi_proc.send("\x1b[A")
    elif pin_name == "JOY_DOWN":
        raspi_proc.send("\x1b[B")
    elif pin_name == "JOY_LEFT":
        raspi_proc.send("\x1b[D")
    elif pin_name == "JOY_RIGHT":
        raspi_proc.send("\x1b[C")
    elif pin_name == "JOY_PRESS" or pin_name == "KEY3":
        raspi_proc.send("\n")
    elif pin_name == "KEY1":
        raspi_proc.sendcontrol("c")
        raspi_proc.terminate(force=True)
        raspi_proc = None
        show_settings_menu()
        return
    draw_raspi_screen()

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
    menu_instance.font = font_medium
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.items = [
        "Display",
        "Wi-Fi Setup",
        "Bluetooth",
        "raspi-config",
        "Toggle Wi-Fi",
        "Shutdown",
        "Git Pull",
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
    menu_instance.items = ["Brightness", "Font", "Text Size", "Color Scheme", "Back"]
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


def show_color_scheme_menu():
    """Allow the user to select a menu color scheme."""
    stop_scrolling()
    menu_instance.items = list(COLOR_SCHEMES.keys()) + ["Back"]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.current_screen = "color_scheme_menu"
    menu_instance.draw()


def handle_display_selection(selection):
    if selection == "Brightness":
        menu_instance.current_screen = "brightness"
        draw_brightness_screen()
    elif selection == "Font":
        show_font_menu()
    elif selection == "Text Size":
        show_text_size_menu()
    elif selection == "Color Scheme":
        show_color_scheme_menu()
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


def handle_color_scheme_selection(selection):
    if selection == "Back":
        show_display_menu()
        return
    apply_color_scheme(selection)
    menu_instance.display_message_screen("Color Scheme", f"{selection} selected", delay=2)
    show_display_menu()


def show_console_color_scheme_menu():
    """Color scheme picker when using the console."""
    stop_scrolling()
    menu_instance.items = list(COLOR_SCHEMES.keys()) + ["Back"]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.current_screen = "console_color_scheme_menu"
    menu_instance.draw()


def handle_console_color_scheme_selection(selection):
    if selection == "Back":
        start_console()
        return
    apply_color_scheme(selection)
    start_console()


def show_bluetooth_menu():
    """Menu for Bluetooth actions."""
    stop_scrolling()
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.items = ["Discover devices", "Pairing mode", "Back"]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "bluetooth_menu"
    menu_instance.draw()


def handle_bluetooth_menu_selection(selection):
    if selection == "Discover devices":
        show_bluetooth_devices()
    elif selection == "Pairing mode":
        start_bluetooth_pairing()
    elif selection == "Back":
        show_settings_menu()


def show_games_menu():
    stop_scrolling()
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.items = [
        "Doctor Mode",
        "Button Game",
        "Launch Codes",
        "Snake",
        "Tetris",
        "Rock Paper Scissors",
        "Space Invaders",
        "Vet Adventure",
        "Axe",
        "Trivia",
        "Two Player Trivia",
        "Mini Games",
        "Hack In",
        "Pico WoW",
        "GTA 1997",
        "Back",
    ]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "games"
    menu_instance.draw()


def handle_games_selection(selection):
    if selection == "Doctor Mode":
        start_doctor_mode()
        return
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
    elif selection == "Two Player Trivia":
        start_two_player_trivia()
        return
    elif selection == "Mini Games":
        start_mini_games()
        return
    elif selection == "Hack In":
        start_hack_in()
        return
    elif selection == "Pico WoW":
        start_pico_wow()
        return
    elif selection == "GTA 1997":
        start_gta_1997()
        return
    elif selection == "Back":
        show_main_menu()


def show_notes_menu():
    """Submenu for Notes with write/read options."""
    stop_scrolling()
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.items = ["Novel Typer", "Write Note", "Read Note"]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "notes_menu"
    menu_instance.draw()


def handle_notes_menu_selection(selection):
    if selection == "Novel Typer":
        start_novel_typer()
        return
    elif selection == "Write Note":
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
        "Shell",
        "Console",
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
    elif selection == "Shell":
        start_shell()
    elif selection == "Console":
        start_console()
    elif selection == "Back":
        show_main_menu()


def show_main_menu():
    global console_mode
    console_mode = False
    stop_cursor()
    stop_scrolling()
    menu_instance.max_visible_items = compute_max_visible_items(menu_instance.font)
    menu_instance.items = [
        "Update and Restart",
        "Games",
        "Notes",
        "Chat",
        "Image Gallery",
        "Utilities",
        "Weather",
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
        show_bluetooth_menu()
    elif selection == "raspi-config":
        start_raspi_config()
    elif selection == "Toggle Wi-Fi":
        toggle_wifi()
    elif selection == "Shutdown":
        menu_instance.display_message_screen("System", "Shutting down...", delay=2)
        print("Shutting down now via systemctl poweroff.")
        subprocess.run(["sudo", "poweroff"], check=True)
        exit()
    elif selection == "Git Pull":
        run_git_pull()
        show_settings_menu()
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
    elif selection == "Weather":
        show_weather()
        return
    elif selection == "Top Stories":
        show_top_stories()
        return
    elif selection == "Settings":
        show_settings_menu()
    
    # After any program finishes, redraw the menu
    menu_instance.draw()

# --- Main Execution ---
if __name__ == "__main__":
    load_settings()
    menu_instance = Menu([])
    connect_irc()
    show_main_menu()
    start_bt_log_monitor()

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
