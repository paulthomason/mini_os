# Mini OS

This repository contains a simple menu-based interface for a Raspberry Pi with an ST7735-based LCD display.

The interface now includes a Settings screen. A **Display** submenu lets you change the LCD backlight brightness, choose a different font and adjust the text size. Additional menu options briefly display the current date and time, a system monitor showing CPU temperature, load, frequency, memory and disk usage, and a network info screen with the current IP address and Wi-Fi SSID. Shutdown and Reboot options are available for safely powering off or restarting the Pi. An "Update and Restart" option pulls the latest code and restarts the service so the update takes effect.

Two small games are included: a reaction-based **Button Game** and a memory challenge called **Launch Codes**. They can be started from the **Games** submenu and make use of the three buttons and joystick directions for input.

An **Image Gallery** viewer is also included. Create an `images/` directory (the program will create it if missing) and place your 128x128 PNG or JPEG files there. When started from the menu you can flip through the pictures using the joystick left and right, and press the joystick in to return to the main menu.

Selecting **Notes** from the main menu now opens a small submenu with **Write Note** and **Read Note**. Write Note launches the onscreen keyboard for taking quick notes. Use the joystick to move the highlight and press it to select a key. The keyboard begins in uppercase mode and automatically switches to lowercase after the first letter is entered. Press **KEY1** to cycle between uppercase, lowercase and punctuation layouts, **KEY2** deletes the last character and **KEY3** saves the note. Read Note shows the text files stored in `/notes`; choose one to read it. When viewing a note press **KEY3** to return to the list and press **KEY3** again to go back to the main menu.

## Setup on Raspberry Pi OS Lite (32-bit)

Install the required packages and enable the SPI interface:

```bash
sudo apt-get update
sudo apt-get install python3-pip python3-rpi.gpio fonts-dejavu-core
sudo pip3 install -r requirements.txt
sudo raspi-config nonint do_spi 0
```

Reboot after enabling SPI so the display can be accessed by the script.

## Pin Assignments

Mini OS uses BCM GPIO numbers. Connect the Waveshare 1.44" ST7735 display and buttons as follows:

### ST7735 Display
- **RST** - GPIO27
- **DC** - GPIO25
- **CS** - GPIO8
- **MOSI** - GPIO10
- **SCLK** - GPIO11
- **Backlight** - GPIO24

### Buttons and Joystick (active LOW)
- **KEY1** - GPIO21
- **KEY2** - GPIO20
- **KEY3** - GPIO16
- **Joystick Up** - GPIO6
- **Joystick Down** - GPIO19
- **Joystick Left** - GPIO5
- **Joystick Right** - GPIO26
- **Joystick Press** - GPIO13

## Running as a `systemd` Service

1. Copy `mini_os.service` to `/etc/systemd/system/` (or `~/.config/systemd/user/` for a user service).
2. Adjust the paths in the unit file if you place the project somewhere other than `/opt/mini_os`.
3. Reload systemd and enable the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable mini_os.service
   sudo systemctl start mini_os.service
   ```

The service definition will start the program on boot and restart it automatically if it exits unexpectedly.

## NYT Top Stories

The menu can fetch headlines from the New York Times API. Copy `nyt_config.py.example` to `nyt_config.py` and add your API key. The file is in `.gitignore` so your key stays local.
