"""Simple Flask-based web server for Mini OS."""

import os
import re
import json
from flask import Flask, request, redirect

app = Flask(__name__)

# Directory for notes relative to this file
NOTES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "notes")
os.makedirs(NOTES_DIR, exist_ok=True)

NYT_API_KEY = None
CHAT_LOG = []
SERVER_RUNNING = False


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
        "<li><a href='/top-stories'>Top Stories</a></li>"
        "</ul>"
    )


@app.route("/settings")
def settings():
    # Basic settings information only
    brightness = globals().get("brightness_level", "N/A")
    font = globals().get("current_font_name", "N/A")
    text_size = globals().get("current_text_size", "N/A")
    return (
        f"<h1>Settings</h1>"
        f"<p>Brightness: {brightness}%</p>"
        f"<p>Font: {font}</p>"
        f"<p>Text Size: {text_size}</p>"
        "<p><a href='/'>Back</a></p>"
    )


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
    global SERVER_RUNNING
    if SERVER_RUNNING:
        return
    SERVER_RUNNING = True
    load_nyt_api_key()
    app.run(host=host, port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    run()
