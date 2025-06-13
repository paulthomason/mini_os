# Veterinary Internal Medicine Quiz Web App

This web application is included with Mini OS to help veterinary technicians improve their knowledge of internal medicine. It provides multiple choice quizzes that can be accessed from the built‑in web interface or directly on the Mini OS display.

## Purpose
The quiz focuses on common topics encountered in veterinary internal medicine. By practicing questions regularly, technicians can reinforce key concepts and identify areas that need additional study.

## Reviewing Missed Questions
At the end of each quiz a review screen lists every question answered incorrectly. Each entry shows the correct option and a short explanation of why it is correct as well as why the other choices are less appropriate. Use the navigation buttons to step through the review.

## Getting Started
1. Install the requirements with `pip3 install -r requirements.txt`.
2. Run `python3 utilities/web_server.py` and open `http://<Pi-IP>:8000`.
3. Start the trivia quiz and answer the questions. After the final score you can review any mistakes before returning to the main menu.

This simple tool aims to make study sessions quick and interactive so learning can happen in short bursts throughout the day.
