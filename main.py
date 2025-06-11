#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time
import subprocess
from datetime import datetime
import os
import random
import threading
import requests
import webbrowser

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

# Pin configuration for luma.lcd
RST_PIN = 27  # GPIO 27 
DC_PIN = 25   # GPIO 25 
# CS (GPIO 8), SCLK (GPIO 11), MOSI (GPIO 10) are handled by the SPI interface directly. 
BL_PIN = 24   # Backlight pin, GPIO 24 

# SPI communication setup (port=0, device=0 corresponds to SPI0 CE0/GPIO 8)
# Speed can be up to 60MHz for ST7735S 
serial_interface = spi(port=0, device=0, cs_high=False,
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
# Try to load a monospace font for better alignment, fallback to default.
try:
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
    font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
except IOError:
    print("Defaulting to PIL built-in font as custom font not found.")
    font_small = ImageFont.load_default()
    font_medium = ImageFont.load_default()
    font_large = ImageFont.load_default()

# --- Backlight Control ---
brightness_level = 100  # Percentage 0-100
backlight_pwm = None

# --- NYT Top Stories ---
nyt_stories = []
current_story_index = 0
try:
    from nyt_config import NYT_API_KEY
except Exception:
    NYT_API_KEY = "YOUR_API_KEY_HERE"


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
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


# --- Menu System ---
class Menu:
    def __init__(self, items, font=font_medium):
        self.items = items
        self.selected_item = 0
        self.font = font
        self.current_screen = "main_menu"  # Tracks which menu/screen is active
        self.view_start = 0  # First visible item index
        # Maximum number of items that fit on the screen
        self.max_visible_items = 6

    def draw(self):
        # Create a new blank image with black background
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
        draw = ImageDraw.Draw(img)

        # Draw header
        draw.text((5, 2), "Mini-OS Menu", font=font_large, fill=(0, 255, 255)) # Cyan header
        draw.line([(0, 18), (DISPLAY_WIDTH, 18)], fill=(255, 255, 255)) # Separator line

        y_offset = 25
        visible_items = self.items[self.view_start:self.view_start + self.max_visible_items]
        for idx, item in enumerate(visible_items):
            i = self.view_start + idx
            text_color = (255, 255, 255)  # White

            # Determine text size using textbbox (compatible with newer Pillow versions)
            bbox = draw.textbbox((0, 0), item, font=self.font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            if i == self.selected_item:
                text_color = (0, 255, 0)  # Green for selected item
                # Draw a selection rectangle
                draw.rectangle(
                    [(2, y_offset - 2), (DISPLAY_WIDTH - 2, y_offset + text_height + 2)],
                    fill=(50, 50, 50),
                )  # Dark gray background for selection

            draw.text((5, y_offset), item, font=self.font, fill=text_color)
            y_offset += text_height + 3  # Line spacing based on font height

        thread_safe_display(img) # Send the PIL image to the display

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
                if menu_instance.get_selected_item() != "Shutdown":
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
                show_settings_menu()
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
        elif menu_instance.current_screen == "nyt_list":
            if pin_name == "JOY_UP":
                menu_instance.navigate("up")
            elif pin_name == "JOY_DOWN":
                menu_instance.navigate("down")
            elif pin_name == "KEY1":
                draw_story_detail(menu_instance.selected_item)
            elif pin_name == "KEY3":
                show_main_menu()
        elif menu_instance.current_screen == "nyt_story":
            if pin_name == "KEY1":
                open_current_story()
            elif pin_name == "KEY3":
                show_top_stories()
        elif menu_instance.current_screen == "button_game":
            if pin_name in BUTTON_NAMES:
                handle_game_input(pin_name)
        elif menu_instance.current_screen == "launch_codes":
            if pin_name in BUTTON_PINS:
                handle_launch_input(pin_name)
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

def run_program1():
    menu_instance.display_message_screen("Program 1", "Running a sample program...", delay=2)
    # Example: Launch an external Python script using subprocess.run()
    # It's important that the subprocess eventually exits.
    try:
        # Absolute path is highly recommended for systemd services
        # Replace '/path/to/your/program1.py' with the actual path
        # If your program needs to interact with the display, it needs to get the 'device' object,
        # or you can pass display commands via a queue/pipe, or render to an off-screen buffer and transfer.
        # For simple programs that just do calculations or log, this is fine.
        print("Launching /home/pi/my_program1.py (replace with actual path)")
        # Example of launching a simple script that prints to console (which goes to journalctl)
        # If your subprocess needs to take over the display directly, it would need to initialize
        # its own luma.lcd device, which can conflict if not managed carefully.
        # For this setup, it's better if external programs are purely text-based
        # or have their own lightweight display methods that don't conflict with luma.lcd.
        # For a truly "mini-OS" feel, subprocesses could render *to* a new PIL image
        # and pass it back to the main_menu to display. This is more complex.
        
        # For this simple example, we'll simulate a program running
        menu_instance.display_message_screen("Program 1", "Doing some work...", delay=3)
        # If the external program needs to run independently and maybe take over the screen completely,
        # you'd need to stop the main menu's display updates and let the subprocess manage it,
        # then re-initialize the main menu's display when the subprocess exits. This is advanced.
        
        # Here, we'll just simulate a blocking operation.
        time.sleep(2) 

        # Example: If your external program is another Python script
        # subprocess.run(["/usr/bin/python3", "/home/pi/my_program1.py"], check=True)

        menu_instance.display_message_screen("Program 1", "Finished!", delay=1.5)
    except FileNotFoundError:
        menu_instance.display_message_screen("Error", "Program 1 script not found!", delay=2)
    except subprocess.CalledProcessError as e:
        menu_instance.display_message_screen("Error", f"Program 1 failed: {e}", delay=3)
    finally:
        # Ensure display is cleared and control returns to menu
        menu_instance.clear_display()


def run_program2():
    menu_instance.display_message_screen("Program 2", "Starting another app...", delay=2)
    time.sleep(2)
    menu_instance.display_message_screen("Program 2", "Done!", delay=1.5)
    menu_instance.clear_display()


def show_top_stories():
    """Fetch and display NYT top stories in a selectable menu."""
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

    titles = []
    dummy_img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    dummy_draw = ImageDraw.Draw(dummy_img)
    for story in nyt_stories:
        lines = wrap_text(story.get("title", ""), font_medium, DISPLAY_WIDTH - 10, dummy_draw)
        titles.append(lines[0])

    menu_instance.items = titles
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "nyt_list"
    menu_instance.draw()


def draw_story_detail(index):
    """Display selected story with scrolling if needed."""
    global scroll_thread, scroll_stop_event, current_story_index
    stop_scrolling()
    current_story_index = index
    menu_instance.current_screen = "nyt_story"
    story = nyt_stories[index]
    header = "NYT Story"
    text = f"{story.get('title','')}\n\n{story.get('abstract','')}"

    dummy_img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    dummy_draw = ImageDraw.Draw(dummy_img)
    max_width = DISPLAY_WIDTH - 10
    lines = wrap_text(text, font_small, max_width, dummy_draw)
    line_h = dummy_draw.textbbox((0, 0), "A", font=font_small)[3] + 2
    available_h = DISPLAY_HEIGHT - 35
    total_h = len(lines) * line_h

    def render(offset=0):
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color="black")
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), header, font=font_large, fill=(255, 255, 0))
        y = 25 - offset
        for line in lines:
            draw.text((5, y), line, font=font_small, fill=(255, 255, 255))
            y += line_h
        draw.text((5, DISPLAY_HEIGHT - 10), "1=Open 3=Back", font=font_small, fill=(0, 255, 255))
        device.display(img)

    if total_h <= available_h:
        render()
    else:
        def scroll_task():
            off = 0
            max_off = total_h - available_h
            while not scroll_stop_event.is_set():
                render(off)
                off = 0 if off >= max_off else off + 1
                time.sleep(0.2)

        scroll_stop_event.clear()
        scroll_thread = threading.Thread(target=scroll_task, daemon=True)
        scroll_thread.start()


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
    networks = []
    try:
        output = subprocess.check_output([
            "nmcli",
            "-t",
            "-f",
            "ssid",
            "dev",
            "wifi",
        ]).decode()
        networks = [line for line in output.splitlines() if line]
    except Exception:
        networks = []

    if not networks:
        networks = ["No Networks Found"]

    networks.append("Back")
    menu_instance.items = networks
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "wifi_list"
    menu_instance.draw()


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
        draw.text((5, 55), f"Mem: {mem_str}", font=font_medium, fill=(255, 255, 255))
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
    stop_scrolling()
    menu_instance.items = ["Brightness", "Wi-Fi Setup", "Back"]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "settings"
    menu_instance.draw()


def show_main_menu():
    stop_scrolling()
    menu_instance.items = [
        "Run Program 1",
        "Run Program 2",
        "Button Game",
        "Launch Codes",
        "System Monitor",
        "Network Info",
        "Top Stories",
        "Date & Time",
        "Show Info",
        "Settings",
        "Shutdown",
    ]
    menu_instance.selected_item = 0
    menu_instance.view_start = 0
    menu_instance.current_screen = "main_menu"
    menu_instance.draw()


def handle_settings_selection(selection):
    if selection == "Brightness":
        menu_instance.current_screen = "brightness"
        draw_brightness_screen()
    elif selection == "Wi-Fi Setup":
        show_wifi_networks()
    elif selection == "Back":
        show_main_menu()

def handle_menu_selection(selection):
    print(f"Selected: {selection}") # This output goes to journalctl
    if selection == "Run Program 1":
        run_program1()
    elif selection == "Run Program 2":
        run_program2()
    elif selection == "Button Game":
        start_button_game()
        return
    elif selection == "Launch Codes":
        start_launch_codes()
        return
    elif selection == "System Monitor":
        run_system_monitor()
    elif selection == "Network Info":
        show_network_info()
    elif selection == "Top Stories":
        show_top_stories()
    elif selection == "Date & Time":
        show_date_time()
    elif selection == "Show Info":
        show_info()
    elif selection == "Settings":
        show_settings_menu()
    elif selection == "Shutdown":
        menu_instance.display_message_screen("System", "Shutting down...", delay=2)
        print("Shutting down now via systemctl poweroff.")
        # Perform actual shutdown. User running service needs permission for this.
        # This typically means adding 'pi ALL=(ALL) NOPASSWD: /sbin/poweroff' to /etc/sudoers
        # OR running the service as root (less secure, not recommended)
        subprocess.run(["sudo", "poweroff"], check=True)
        # If shutdown fails or doesn't happen fast enough, script might continue.
        # For robustness, you might want to exit the script after the poweroff command.
        exit() # Exit the Python script as OS is shutting down
    
    # After any program finishes, redraw the menu
    menu_instance.draw()

# --- Main Execution ---
if __name__ == "__main__":
    menu_instance = Menu([])
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
