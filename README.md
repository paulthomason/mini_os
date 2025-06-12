# Mini OS

This repository contains a simple menu-based interface for a Raspberry Pi with an ST7735-based LCD display.

The interface now includes a Settings screen. A **Display** submenu lets you change the LCD backlight brightness, choose a different font and adjust the text size. Additional menu options briefly display the current date and time, a system monitor showing CPU temperature, load, frequency, memory and disk usage, and a network info screen with the current IP address and Wi-Fi SSID. Shutdown and Reboot options are available at the bottom of the Settings screen for safely powering off or restarting the Pi. An "Update and Restart" option pulls the latest code and restarts the service so the update takes effect.

Several small games are included: the reaction-based **Button Game**, the memory challenge **Launch Codes**, classics like **Snake** and **Tetris**, a simple **Rock Paper Scissors**, **Space Invaders**, and a text based adventure called **Vet Adventure**. Recent additions like **Axe**, **Trivia**, **Hack In**, and **Pico WoW** round out the selection. They can be started from the **Games** submenu and make use of the three buttons and joystick directions for input.

An **Image Gallery** viewer is also included. Create an `images/` directory (the program will create it if missing) and place your 128x128 PNG or JPEG files there. When started from the menu you can flip through the pictures using the joystick left and right, and press the joystick in to return to the main menu.

Selecting **Notes** from the main menu now opens a small submenu with **Novel Typer**, **Write Note** and **Read Note**. Write Note launches the onscreen keyboard for taking quick notes. Use the joystick to move the highlight and press it to select a key. The keyboard begins in uppercase mode and automatically switches to lowercase after the first letter is entered. Press **KEY1** to cycle between uppercase, lowercase and punctuation layouts, **KEY2** deletes the last character and **KEY3** saves the note. Novel Typer is an experimental text input method that uses all buttons and joystick directions: KEY1 changes letter pages, KEY2 deletes characters and KEY3 confirms the highlighted letter or exits. Read Note shows the text files stored in `/notes`; choose one to read it. While viewing a note you can press **KEY1** to edit the note, **KEY2** to delete it, and **KEY3** to return to the list (press **KEY3** again to go back to the main menu).

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

## Web Interface

A lightweight web server can be started from the **Utilities** menu. It exposes
a simple browser based interface for viewing and updating settings. From the
`/settings` page you can change the display brightness, select a font and adjust
the text size. Wi-Fi can also be toggled on or off directly from the browser.

The server requires the Python packages listed in `requirements.txt`
(including **Flask** and **pexpect**). Install them with `pip3 install -r
requirements.txt` and then either select **Web Server** from the Utilities menu
or run `python3 utilities/web_server.py` manually. Once running, visit
`http://<Pi-IP>:8000` in your browser.

### Shell (`/shell`)

The web interface provides a simple shell at `/shell`. Enter a command and press
**Run** to execute it; output from the last few commands appears below the form.
Commands run as the same user that started the server. If a command uses `sudo`
and a password is required, the web page cannot supply it, so the command will
fail unless the server was started with the necessary privileges. Exposing this
web shell on a network lets anyone execute commands on your Pi, so only enable
it on trusted networks or behind a firewall.

### Interactive Shell

Opening `/shell` in a browser now provides a live Bash prompt. Commands are
executed in a persistent shell so each one can build on the previous. If a
command asks for a password (for example when using `sudo`), a password field
will appear so you can respond directly in the browser.

**Security Warning:** anyone who can access this page can run arbitrary commands
on your Pi. Only enable the web server on trusted networks and consider adding
additional authentication if it is exposed beyond localhost.

## Wi-Fi

Choose **Wi-Fi Setup** from the Settings menu to scan for nearby
networks. Select one and press **KEY3** to connect. Set the environment
variable `MINI_OS_WIFI_PASSWORD` before starting Mini OS so `nmcli` can
use it to connect without prompting for the password.

## Bluetooth

From **Settings** choose **Bluetooth** to scan for nearby devices. Select your
iPhone or other device with the joystick. Press **KEY1** to attempt a direct
connection or **KEY2** to pair and connect (useful for phones that require
confirming a passkey such as the iPhone 15 Pro Max). Ensure the phone is in
Bluetooth pairing mode when attempting to connect.

Scanning now falls back to `bluetoothctl` if `hcitool` is unavailable and
connection failures will display the full output from `bluetoothctl` so you can
see exactly why a device did not connect. Each failure is also saved in the
`notes` directory as `btfail1.txt`, `btfail2.txt` and so on for later review.

The Bluetooth device list now uses a smaller font so long names fit on the
screen without running off the edge. Device names are displayed before their
Bluetooth addresses for quicker identification.

The Utilities menu also includes **Shell**, which opens the on-screen keyboard
so you can type a command and execute it on the Pi. Press **KEY1** to cycle the
keyboard layout, **KEY2** to delete the last character and **KEY3** to run the
command. The output scrolls on the display and pressing **KEY3** returns to the
prompt.

