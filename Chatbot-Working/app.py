from flask import Flask, render_template, request, redirect, url_for, session, jsonify,send_file,Response
import cv2
from deepface import DeepFace
import time
import threading
import os
import json
from datetime import datetime
import sqlite3
from flask_session import Session
import requests
import os
import re

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key")  # Replace with a secure key in production
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# SQLite Database Connection
def get_db_connection():
    try:
        conn = sqlite3.connect("database.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as err:
        print(f"Error connecting to database: {err}")
        return None

db = get_db_connection()

# Initialize DB schema if not exists
with db:
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            userid TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    """)

# Emotion tracking file path
MEMORY_FILE = os.path.join("data/emotions.json")

# Ensure the 'data' directory exists
if not os.path.exists(os.path.dirname(MEMORY_FILE)):
    os.makedirs(os.path.dirname(MEMORY_FILE))

# Function to load latest emotion
def load_latest_emotion():
    # Ensure the file exists before attempting to read
    if not os.path.exists(MEMORY_FILE):
        print("Emotion file not found, creating a new one.")
        with open(MEMORY_FILE, "w") as file:
            json.dump([], file)  # Initialize with an empty list
        return "neutral"

    try:
        with open(MEMORY_FILE, 'r') as file:
            emotions = json.load(file)

            # Validate data structure
            if isinstance(emotions, list) and emotions:
                return emotions[-1].get("emotion","neutral")

    except json.JSONDecodeError:
        print("Error: Corrupt emotions.json file. Attempting recovery.")
        with open(MEMORY_FILE, "w") as file:
            json.dump([], file)  # Reset the file completely
        return "neutral"

    except Exception as e:
        print(f"Error loading emotion data: {e}")
        return "neutral"

#Stores emotion
def store_emotion(emotion):
    try:
        if not os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'w') as file:
                json.dump([], file)

        with open(MEMORY_FILE, 'r') as file:
            try:
                emotions = json.load(file)
                if not isinstance(emotions, list):
                    emotions = []
            except json.JSONDecodeError:
                emotions = []

        new_entry = {"timestamp": str(datetime.now()), "emotion": emotion}
        emotions.append(new_entry)
        emotions = emotions[-7:]

        with open(MEMORY_FILE, 'w') as file:
            json.dump(emotions, file, indent=4)
    except Exception as e:
        print(f"Error storing emotion: {e}")

# Function to capture emotion continuously
def capture_emotion():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Camera not accessible")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame")
            break
        try:
            analysis = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            if analysis and isinstance(analysis, list) and 'dominant_emotion' in analysis[0]:
                dominant_emotion = analysis[0]['dominant_emotion']
                print(f"Detected Emotion: {dominant_emotion}")
                store_emotion(dominant_emotion)
        except Exception as e:
            print(f"Emotion detection error: {e}")
        time.sleep(3)

    cap.release()
    cv2.destroyAllWindows()

threading.Thread(target=capture_emotion, daemon=True).start()

# Home Route
@app.route('/')
def home():
    return render_template('home.html')

# Sign Up Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        userid = request.form['userid']
        email = request.form['email']
        password = request.form['password']

        try:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM users WHERE userid = ? OR email = ?", (userid, email))
            existing_user = cursor.fetchone()

            if existing_user:
                if existing_user['userid'] == userid and existing_user['email'] == email:
                    error = "Both User ID and Email are already taken. Please use different ones."
                elif existing_user['userid'] == userid:
                    error = "User ID is already taken. Please choose a different one."
                elif existing_user['email'] == email:
                    error = "Email is already taken. Please use a different email."
                return render_template('signup.html', error=error)

            cursor.execute("INSERT INTO users (name, userid, email, password) VALUES (?, ?, ?, ?)",
                           (name, userid, email, password))
            db.commit()
            return redirect(url_for('signin'))

        except sqlite3.Error as e:
            error = f"Database Error: {str(e)}"
            return render_template('signup.html', error=error)

    return render_template('signup.html')

# Sign In Route
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        userid = request.form['userid']
        password = request.form['password']

        try:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM users WHERE userid = ? AND password = ?", (userid, password))
            user = cursor.fetchone()

            if user:
                session['userid'] = user['userid']
                session['name'] = user['name']
                return redirect(url_for('dashboard'))
            else:
                error = "Invalid User ID or Password. Please try again."
                return render_template('signin.html', error=error)

        except sqlite3.Error as e:
            error = f"Database Error: {str(e)}"
            return render_template('signin.html', error=error)

    return render_template('signin.html')

# Dashboard Route
@app.route('/dashboard')
def dashboard():
    if 'userid' in session:
        return render_template('dashboard.html', name=session['name'])
    else:
        return redirect(url_for('signin'))

# Logout Route
@app.route('/logout')
def logout():
    session.pop('userid', None)
    session.pop('name', None)
    return redirect(url_for('signin'))

def analyze_emotion_trend():
    try:
        with open(MEMORY_FILE, 'r') as file:
            emotions = json.load(file)
            return emotions,[]  # ✅ Return the raw emotion data (list of dicts)

    except Exception as e:
        print(f"Error reading emotion file: {e}")
        return "netral",[]

def chat_with_llama3(user_input):
    api_key = os.getenv("OPENROUTER_API_KEY")
    endpoint = "https://openrouter.ai/api/v1/chat/completions"

    dominant_trend, recent_emotions = analyze_emotion_trend()

    emotional_context = (
    f"Recently, the user has mostly felt '{dominant_trend}' "
    f"(e.g., {', '.join(recent_emotions)}). "
    "Respond like a caring friend—be empathetic, supportive, and uplifting if they're sad, anxious or angry; share in their joy if they're doing well."
    )

    system_prompt = (
    "You are an emotionally aware and caring AI friend. "
    "Be thoughtful, kind, and keep responses short. "
    f"{emotional_context}"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost"
    }

    data = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input.strip()}
        ]
    }

    try:
        response = requests.post(endpoint, headers=headers, json=data)
        response.raise_for_status()
        raw_message = response.json()["choices"][0]["message"]["content"]
        cleaned_message = re.sub(r'\*+', '', raw_message)
        return cleaned_message

    except Exception as e:
        return f"Error during AI response: {e}"

# === Chat route ===
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if "history" not in session:
        session["history"] = []

    if request.method == 'POST':
        data = request.form.get("message", "") or request.json.get("message", "")
        
        if data:
            user_message = data.strip()
            bot_response = chat_with_llama3(user_message)

            session["history"].append({"role": "user", "message": user_message})
            session["history"].append({"role": "bot", "message": bot_response})
            session.modified = True

    return render_template('chatbot.html', chat_history=session.get("history", []))

@app.route('/clear')
def clear_chat():
    session.pop("history", None)
    return redirect("/chat")

if __name__ == '__main__':
    app.run(debug=True)