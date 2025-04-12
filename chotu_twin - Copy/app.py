from flask import Flask, render_template, request, jsonify, Response
from faster_whisper import WhisperModel
from gtts import gTTS
import requests
import os
import tempfile
import io

app = Flask(__name__)

# Set up Whisper STT model (using tiny for Render compatibility)
try:
    stt_model = WhisperModel("tiny.en", device="cpu")  # Use 'tiny' model for lightweight deployment
except Exception as e:
    raise RuntimeError(f"Failed to load Whisper model: {e}")

# Set your OpenRouter API Key (if using AI response)
OPENROUTER_API_KEY = "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"

# Homepage
@app.route("/")
def index():
    return render_template("index.html")

# Speech-to-Text (STT)
@app.route("/stt", methods=["POST"])
def speech_to_text():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file received"}), 400

    audio_file = request.files["audio"]
    temp_audio_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio_file:
            audio_file.save(temp_audio_file)
            temp_audio_path = temp_audio_file.name

        print(f"Processing audio file at: {temp_audio_path}")
        segments, _ = stt_model.transcribe(temp_audio_path, beam_size=5)
        transcribed_text = " ".join([segment.text for segment in segments]).strip()
        print(f"Transcribed text: {transcribed_text}")

        if not transcribed_text:
            return jsonify({"error": "Transcription failed or was empty"}), 500

        ai_message = get_ai_response(transcribed_text)
        print(f"AI Response: {ai_message}")
        tts_audio = convert_text_to_speech(ai_message)

    except Exception as e:
        print(f"Error during transcription: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        if temp_audio_path is not None and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

    return jsonify({
        "transcribed_text": transcribed_text,
        "ai_response": ai_message,
        "tts_audio_url": "/tts_audio",
    })

# AI response via OpenRouter
def get_ai_response(user_input):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [{"role": "user", "content": f"{user_input} (Respond briefly in 2-3 sentences)"}],
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        ai_message = response.json()["choices"][0]["message"]["content"].strip()
        return ai_message

    except Exception as e:
        print(f"OpenRouter Error: {e}")
        return "I'm sorry, I couldn't process your request right now."

# Convert text to speech
def convert_text_to_speech(text):
    tts = gTTS(text=text, lang='en')
    audio_data = io.BytesIO()
    tts.write_to_fp(audio_data)
    audio_data.seek(0)
    return audio_data

# Serve TTS audio (POST request with text)
@app.route("/tts_audio", methods=["POST"])
def tts_audio():
    data = request.get_json()
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        tts = gTTS(text=text, lang='en')
        audio_data = io.BytesIO()
        tts.write_to_fp(audio_data)
        audio_data.seek(0)
        return Response(audio_data, mimetype="audio/mpeg")

    except Exception as e:
        print(f"Error during TTS: {e}")
        return jsonify({"error": str(e)}), 500

# Entry point for local testing or Render startup
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # fallback to 10000 if not set (good for local dev)
    app.run(host="0.0.0.0", port=port, debug=False)