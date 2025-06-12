"""Simple Flask-based web server for Mini OS."""

import os
import re
import json
import threading
import importlib
import subprocess
import pexpect
from flask import Flask, request, redirect
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

# Directory for notes relative to this file
NOTES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "notes")
os.makedirs(NOTES_DIR, exist_ok=True)

NYT_API_KEY = None
CHAT_LOG = []


@sock.route("/shell/ws")
def shell_ws(ws):
    """WebSocket endpoint for interactive shell."""
    proc = pexpect.spawn("/bin/bash", encoding="utf-8", echo=False)

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
        "<li><a href='/top-stories'>Top Stories</a></li>"
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
    <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/xterm/css/xterm.css'>
    <style>
        body { background: black; margin: 0; }
        #terminal { height: 100vh; width: 100%; }
        .xterm { color: #0f0; background: black; }
    </style>
    </head>
    <body>
    <div id='terminal'></div>
    <script src='https://cdn.jsdelivr.net/npm/xterm/lib/xterm.js'></script>
    <script>
        const term = new Terminal({cursorBlink: true});
        term.open(document.getElementById('terminal'));
        const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
        const socket = new WebSocket(protocol + location.host + '/shell/ws');
        term.onData(d => socket.send(d));
        socket.onmessage = e => term.write(e.data);
        socket.onclose = () => term.write('\r\n[Disconnected]');
    </script>
    </body>
    </html>
    """


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
