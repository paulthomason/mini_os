"""Simple Flask-based web server for Mini OS."""

import os
import re
import json
import threading
import importlib
import subprocess
import pexpect
from flask import Flask, request, redirect, send_from_directory
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

# Directory for notes relative to this file
NOTES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "notes")
os.makedirs(NOTES_DIR, exist_ok=True)

NYT_API_KEY = None
CHAT_LOG = []

WEB_GAMES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web_games")
os.makedirs(WEB_GAMES_DIR, exist_ok=True)

# Directory for static assets used by the web interface
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

@sock.route("/shell/ws")
def shell_ws(ws):
    """WebSocket endpoint for interactive shell."""
    # Start Bash in interactive mode so prompts display correctly
    proc = pexpect.spawn("/bin/bash", ["-i"], encoding="utf-8", echo=False)
    # Ensure an initial prompt appears
    proc.sendline("")

    def read_output():
        try:
            while True:
                data = proc.read_nonblocking(size=1024, timeout=0.1)
                if data:
                    ws.send(data)
        except pexpect.exceptions.EOF:
            ws.send("\n[Process terminated]")
        except Exception:
            pass

    t = threading.Thread(target=read_output, daemon=True)
    t.start()

    while True:
        msg = ws.receive()
        if msg is None:
            break
        proc.send(msg)

    proc.close()


def load_nyt_api_key():
    """Try to load NYT API key from nyt_config.py"""
    global NYT_API_KEY
    try:
        from nyt_config import NYT_API_KEY as KEY
        NYT_API_KEY = KEY
    except Exception:
        NYT_API_KEY = "YOUR_API_KEY_HERE"


@app.route("/")
def index():
    return (
        "<h1>Mini OS Web Interface</h1>"
        "<ul>"
        "<li><a href='/settings'>Settings</a></li>"
        "<li><a href='/notes'>Notes</a></li>"
        "<li><a href='/chat'>Chat</a></li>"
        "<li><a href='/shell'>Shell</a></li>"
        "<li><a href='/weather'>Weather</a></li>"
        "<li><a href='/top-stories'>Top Stories</a></li>"
        "<li><a href='/mini-games'>Mini Games</a></li>"
        "</ul>"
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    """Display and modify Mini OS settings."""
    main = importlib.import_module("__main__")

    if request.method == "POST":
        b = request.form.get("brightness")
        if b is not None and b != "":
            try:
                val = max(0, min(100, int(b)))
                if hasattr(main, "brightness_level"):
                    main.brightness_level = val
                    if hasattr(main, "update_backlight"):
                        main.update_backlight()
            except ValueError:
                pass

        font = request.form.get("font")
        if font and hasattr(main, "AVAILABLE_FONTS") and font in main.AVAILABLE_FONTS:
            main.current_font_name = font
            if hasattr(main, "update_fonts"):
                main.update_fonts()

        size = request.form.get("text_size")
        if size and hasattr(main, "TEXT_SIZE_MAP") and size in main.TEXT_SIZE_MAP:
            main.current_text_size = size
            if hasattr(main, "update_fonts"):
                main.update_fonts()

        scheme = request.form.get("color_scheme")
        if scheme and hasattr(main, "COLOR_SCHEMES") and scheme in main.COLOR_SCHEMES:
            if hasattr(main, "apply_color_scheme"):
                main.apply_color_scheme(scheme)

        return redirect("/settings")

    brightness = getattr(main, "brightness_level", "N/A")
    font = getattr(main, "current_font_name", "N/A")
    text_size = getattr(main, "current_text_size", "N/A")
    color_scheme = getattr(main, "current_color_scheme_name", "Default")
    fonts = getattr(main, "AVAILABLE_FONTS", {}).keys()
    sizes = getattr(main, "TEXT_SIZE_MAP", {}).keys()
    schemes = getattr(main, "COLOR_SCHEMES", {}).keys()

    html = ["<h1>Settings</h1>", "<form method='post'>"]
    html.append(
        f"Brightness: <input type='number' name='brightness' min='0' max='100' value='{brightness}'><br>"
    )
    html.append("Font: <select name='font'>")
    for f in fonts:
        sel = "selected" if f == font else ""
        html.append(f"<option value='{f}' {sel}>{f}</option>")
    html.append("</select><br>")
    html.append("Text Size: <select name='text_size'>")
    for s in sizes:
        sel = "selected" if s == text_size else ""
        html.append(f"<option value='{s}' {sel}>{s}</option>")
    html.append("</select><br>")
    html.append("Color Scheme: <select name='color_scheme'>")
    for c in schemes:
        sel = "selected" if c == color_scheme else ""
        html.append(f"<option value='{c}' {sel}>{c}</option>")
    html.append("</select><br>")
    html.append("<button type='submit'>Save</button></form>")
    html.append(
        "<form method='post' action='/toggle-wifi'><button type='submit'>Toggle Wi-Fi</button></form>"
    )
    html.append("<p><a href='/'>Back</a></p>")
    return "\n".join(html)


@app.route("/toggle-wifi", methods=["POST"])
def toggle_wifi_route():
    """Toggle Wi-Fi radio using main module helper."""
    main = importlib.import_module("__main__")
    if hasattr(main, "toggle_wifi"):
        threading.Thread(target=main.toggle_wifi).start()
    return redirect("/settings")


@app.route("/notes", methods=["GET", "POST"])
def notes():
    if request.method == "POST":
        text = request.form.get("text", "").strip()
        if text:
            pattern = re.compile(r"note(\d+)\.txt")
            existing = [
                int(m.group(1))
                for m in (pattern.match(f) for f in os.listdir(NOTES_DIR))
                if m
            ]
            next_num = max(existing, default=0) + 1
            with open(os.path.join(NOTES_DIR, f"note{next_num}.txt"), "w") as f:
                f.write(text)
        return redirect("/notes")

    notes_list = []
    for fname in sorted(os.listdir(NOTES_DIR)):
        if fname.lower().endswith(".txt"):
            with open(os.path.join(NOTES_DIR, fname)) as f:
                notes_list.append((fname, f.read()))
    html = ["<h1>Notes</h1>"]
    html.append("<form method='post'><textarea name='text'></textarea><br>"
                "<button type='submit'>Save</button></form>")
    for name, content in notes_list:
        html.append(f"<h3>{name}</h3><pre>{content}</pre>")
    html.append("<p><a href='/'>Back</a></p>")
    return "\n".join(html)


@app.route("/chat", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        msg = request.form.get("msg", "").strip()
        if msg:
            CHAT_LOG.append(msg)
        return redirect("/chat")

    html = ["<h1>Chat</h1>"]
    html.append("<form method='post'><input name='msg'><button type='submit'>Send</button></form>")
    for line in CHAT_LOG[-50:]:
        html.append(f"<div>{line}</div>")
    html.append("<p><a href='/'>Back</a></p>")
    return "\n".join(html)


@app.route("/shell")
def shell():
    """Serve interactive shell page."""
    return """
    <!doctype html>
    <html>
    <head>
    <link rel='stylesheet' href='/static/xterm.css'>
    <style>
        body { background: black; margin: 0; }
        #terminal { height: 100vh; width: 100%; }
        .xterm { color: #0f0; background: black; }
    </style>
    </head>
    <body>
    <div id='terminal'></div>
    <script src='/static/xterm.js'></script>
    <script>
        const term = new Terminal({cursorBlink: true});
        term.open(document.getElementById('terminal'));
        const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
        const socket = new WebSocket(protocol + location.host + '/shell/ws');
        socket.onopen = () => term.focus();
        term.onData(d => socket.send(d));
        socket.onmessage = e => term.write(e.data);
        // Send a CRLF sequence when the WebSocket closes
        // Use double escaping so the JS string contains "\\r\\n"
        socket.onclose = () => term.write("\\r\\n[Disconnected]");
        
    </script>
    </body>
    </html>
    """


@app.route("/mini-games")
def mini_games_index():
    """Serve the mini games menu page."""
    return send_from_directory(WEB_GAMES_DIR, "index.html")


@app.route("/mini-games/<path:filename>")
def mini_games_static(filename):
    """Serve static files for mini games."""
    return send_from_directory(WEB_GAMES_DIR, filename)


@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve static assets like JavaScript and CSS."""
    return send_from_directory(STATIC_DIR, filename)


# --- Weather Page Helpers ---
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

WEATHER_EMOJI = {
    0: "☀️",
    1: "🌤️",
    2: "⛅",
    3: "☁️",
    45: "🌫️",
    48: "🌫️",
    51: "🌧️",
    53: "🌧️",
    55: "🌧️",
    56: "🌧️",
    57: "🌧️",
    61: "🌧️",
    63: "🌧️",
    65: "🌧️",
    66: "🌧️",
    67: "🌧️",
    71: "❄️",
    73: "❄️",
    75: "❄️",
    77: "❄️",
    80: "🌧️",
    81: "🌧️",
    82: "🌧️",
    85: "❄️",
    86: "❄️",
    95: "⛈️",
    96: "⛈️",
    99: "⛈️",
}


def fetch_weather_data(zip_code):
    """Fetch weather info for a US ZIP code using open-meteo."""
    try:
        import requests
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
        import requests
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
    return {"temp": temp, "desc": desc, "code": code, "high": high, "low": low, "forecast": forecast}


@app.route("/weather")
def weather():
    """Display basic weather info for a ZIP code."""
    main = importlib.import_module("__main__")
    zips = getattr(main, "WEATHER_ZIPS", ["97222"])
    zip_code = request.args.get("zip", zips[0])
    data = fetch_weather_data(zip_code)

    icon = WEATHER_EMOJI.get(data["code"], "") if data else ""
    desc = data["desc"] if data else "N/A"
    temp = f"{data['temp']:.1f}F" if data and data["temp"] is not None else "N/A"
    hi_lo = ""
    if data and data["high"] is not None and data["low"] is not None:
        hi_lo = f"H:{data['high']:.1f}F L:{data['low']:.1f}F"

    html = [
        "<!doctype html>",
        "<html>",
        "<head>",
        "<meta charset='utf-8'>",
        "<title>Weather</title>",
        "<style>body{font-family:Arial, sans-serif;background:#111;color:#eee;padding:1em;}"
        ".icon{font-size:64px;}</style>",
        "</head>",
        "<body>",
        f"<h1>Weather {zip_code}</h1>",
    ]
    if data:
        html.append(f"<div class='icon'>{icon}</div>")
        html.append(f"<p>{desc}</p>")
        html.append(f"<p>Temp: {temp}</p>")
        if hi_lo:
            html.append(f"<p>{hi_lo}</p>")
        if data.get("forecast"):
            html.append("<h2>Forecast</h2><ul>")
            for fc in data["forecast"][1:4]:
                html.append(
                    f"<li>{fc['date']}: H {fc['high']:.1f}F L {fc['low']:.1f}F</li>"
                )
            html.append("</ul>")
    else:
        html.append("<p>Failed to fetch weather data.</p>")
    html.append("<p><a href='/'>Back</a></p>")
    html.append("</body></html>")
    return "\n".join(html)

@app.route("/top-stories")
def top_stories():
    load_nyt_api_key()
    try:
        import requests
        resp = requests.get(
            f"https://api.nytimes.com/svc/topstories/v2/home.json?api-key={NYT_API_KEY}",
            timeout=5,
        )
        data = resp.json()
        stories = data.get("results", [])[:10]
    except Exception:
        stories = []
    html = ["<h1>Top Stories</h1>"]
    if not stories:
        html.append("<p>Failed to fetch stories.</p>")
    else:
        html.append("<ul>")
        for s in stories:
            title = s.get("title", "")
            html.append(f"<li>{title}</li>")
        html.append("</ul>")
    html.append("<p><a href='/'>Back</a></p>")
    return "\n".join(html)


def run(host="0.0.0.0", port=8000):
    """Start the web server."""
    load_nyt_api_key()
    app.run(host=host, port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    run()
