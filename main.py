import RPi.GPIO as GPIO
import time
import subprocess
from datetime import datetime

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

# --- Joystick and Button Configuration ---
# GPIO setup using BCM numbering. Buttons are active LOW (pressed = low). 
GPIO.setmode(GPIO.BCM)

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

# --- Menu System ---
class Menu:
    def __init__(self, items, font=font_medium):
        self.items = items
        self.selected_item = 0
        self.font = font
        self.current_screen = "main_menu" # Tracks which menu/screen is active

    def draw(self):
        # Create a new blank image with black background
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
        draw = ImageDraw.Draw(img)

        # Draw header
        draw.text((5, 2), "Mini-OS Menu", font=font_large, fill=(0, 255, 255)) # Cyan header
        draw.line([(0, 18), (DISPLAY_WIDTH, 18)], fill=(255, 255, 255)) # Separator line

        y_offset = 25
        for i, item in enumerate(self.items):
            text_color = (255, 255, 255) # White
            if i == self.selected_item:
                text_color = (0, 255, 0) # Green for selected item
                # Draw a selection rectangle
                text_width, text_height = draw.textsize(item, font=self.font)
                draw.rectangle([(2, y_offset - 2), (DISPLAY_WIDTH - 2, y_offset + text_height + 2)], 
                               fill=(50, 50, 50)) # Dark gray background for selection
            
            draw.text((5, y_offset), item, font=self.font, fill=text_color)
            y_offset += self.font.getsize(item)[1] + 3 # Line spacing based on font height

        device.display(img) # Send the PIL image to the display

    def navigate(self, direction):
        if direction == "up":
            self.selected_item = (self.selected_item - 1) % len(self.items)
        elif direction == "down":
            self.selected_item = (self.selected_item + 1) % len(self.items)
        self.draw() # Redraw menu after navigation

    def get_selected_item(self):
        return self.items[self.selected_item]

    def display_message_screen(self, title, message, delay=3, clear_after=True):
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), title, font=font_large, fill=(255, 255, 0)) # Yellow title
        draw.text((5, 25), message, font=font_medium, fill=(255, 255, 255)) # White message
        device.display(img)
        time.sleep(delay)
        if clear_after:
            self.clear_display()

    def clear_display(self):
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
        device.display(img)

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
            elif pin_name == "KEY1": # Example: KEY1 acts as a "back" or "cancel" button
                # For main menu, maybe go to a "shutdown/reboot" confirmation
                if menu_instance.get_selected_item() != "Shutdown": # Avoid double-triggering shutdown
                    menu_instance.selected_item = len(menu_instance.items) - 1 # Select shutdown option
                    menu_instance.draw()
            elif pin_name == "KEY2": # Example: Key2 for quick info
                show_info()
                menu_instance.draw() # Return to menu after info
        # You can add more conditions here for other screens/sub-menus
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

def show_info():
    menu_instance.display_message_screen("System Info", "Raspberry Pi Mini-OS\nVersion 1.0\nST7735S Display", delay=4)
    menu_instance.clear_display()

def handle_menu_selection(selection):
    print(f"Selected: {selection}") # This output goes to journalctl
    if selection == "Run Program 1":
        run_program1()
    elif selection == "Run Program 2":
        run_program2()
    elif selection == "Show Info":
        show_info()
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
    menu_items = ["Run Program 1", "Run Program 2", "Show Info", "Shutdown"]
    menu_instance = Menu(menu_items)

    # Attach event detection to all desired pins after the menu is ready
    for pin_name, pin_num in BUTTON_PINS.items():
        # Detect both rising and falling edges to track press/release for robustness
        GPIO.add_event_detect(pin_num, GPIO.BOTH, callback=button_event_handler, bouncetime=100)
        # bouncetime in ms helps filter out noise.

    try:
        # Initialize backlight control
        GPIO.setup(BL_PIN, GPIO.OUT)
        GPIO.output(BL_PIN, GPIO.HIGH) # Turn on backlight 

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
            GPIO.output(BL_PIN, GPIO.LOW) # Turn off backlight
            device.cleanup() # Releases luma.lcd resources
        except Exception as cleanup_e:
            print(f"Error during cleanup: {cleanup_e}")
        GPIO.cleanup() # Always clean up GPIO 
        print("Mini-OS Exited.")
