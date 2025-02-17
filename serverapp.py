from flask import Flask, request, jsonify
import io
import librosa
import numpy as np
import torch
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import boto3

app = Flask(__name__)

# -------------------------------
# 1. Load Whisper model and processor
# -------------------------------
model_name = "openai/whisper-large-v3"  # Standard Whisper model
processor = WhisperProcessor.from_pretrained(model_name)
model = WhisperForConditionalGeneration.from_pretrained(model_name)

device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)

# -------------------------------
# 2. Set up AWS Translate client
# -------------------------------
# Replace these with your actual AWS credentials or use a secure method
aws_access_key_id = "INSERT_YOUR_KEY"
aws_secret_access_key = "INSERT_YOUR_KEY"
aws_region = "INSERT_YOUR_REGION"

translate_client = boto3.client(
    'translate',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region
)

def translate_text(text, source_language, target_language):
    """
    Translate the given text using AWS Translate.
    """
    try:
        response = translate_client.translate_text(
            Text=text,
            SourceLanguageCode=source_language,
            TargetLanguageCode=target_language
        )
        translated_text = response.get("TranslatedText", "")
        return translated_text
    except Exception as e:
        print(f"Translation error: {e}")
        return None

# -------------------------------
# 3. Define the Flask endpoint for file upload
# -------------------------------
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']

    # Read the file into a BytesIO object
    audio_bytes = file.read()
    audio_file = io.BytesIO(audio_bytes)

    # Load audio using librosa and convert to 16kHz
    waveform, sr = librosa.load(audio_file, sr=16000)

    # Ensure waveform has the correct shape (batch dimension)
    waveform = np.expand_dims(waveform, axis=0)

    # Process waveform with Whisper's processor
    inputs = processor(waveform, sampling_rate=16000, return_tensors="pt")
    input_features = inputs.input_features.to(device)

    # Generate transcription using Whisper
    predicted_ids = model.generate(input_features)
    transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

    # -------------------------------
    # 4. Translate the transcription using AWS Translate
    # -------------------------------
    
    source_lang = request.form.get("source_language", "ru")
    target_lang = request.form.get("target_language", "en")

    translation = translate_text(transcription, source_lang, target_lang)

    return jsonify({
        "transcription": transcription,
        "translation": translation
    })

# -------------------------------
# 5. Run the Flask server
# -------------------------------
if __name__ == '__main__':
    # Listen on all network interfaces so other computers on your network can reach it
    app.run(host='0.0.0.0', port=8000)
