# Mini OS

This repository contains a simple menu-based interface for a Raspberry Pi with an ST7735-based LCD display.

The interface now includes a basic Settings screen where you can adjust the LCD backlight brightness using the joystick. It also provides menu options to briefly display the current date and time, a simple system monitor showing CPU temperature, load and memory usage, and a network info screen showing the current IP address and Wi-Fi SSID. A Shutdown and Reboot option are available for safely powering off or restarting the Pi. An "Update Mini-OS" entry pulls the latest code with `git pull`.

Two small games are included: a reaction-based **Button Game** and a memory challenge called **Launch Codes**. Both can be started from the main menu and make use of the three buttons and joystick directions for input.

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
