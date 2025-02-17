import pyaudio
import wave
import collections
import time
import keyboard
import requests
import os
import threading
import tkinter as tk
from tkinter import scrolledtext

# CONFIGURABLE PARAMS
CHUNK = 1024               # Number of frames per buffer read
FORMAT = pyaudio.paInt16   # 16-bit audio
CHANNELS = 2               # Stereo
RATE = 48000               # 48kHz sample rate
SECONDS = 20               # Rolling buffer length (in seconds)

# Device index (update based on your system)
DEVICE_INDEX = 3

# Calculate how many chunks fit into SECONDS seconds
NUM_CHUNKS_IN_BUFFER = int(RATE / CHUNK * SECONDS)

# Create a ring buffer using collections.deque with a fixed maxlen
audio_buffer = collections.deque(maxlen=NUM_CHUNKS_IN_BUFFER)

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open the stream with the specified input device index
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    input_device_index=DEVICE_INDEX,
    frames_per_buffer=CHUNK
)

# Flask endpoint URL
endpoint_url = "http://localhost:8000/upload"

# GUI Setup
root = tk.Tk()
root.title("Audio Recorder & Processor")
root.geometry("1000x600")
root.configure(bg='black')

# ScrolledText for output
output_text = scrolledtext.ScrolledText(
    root,
    wrap='word',    # Ensure text doesn't break mid-word
    width=80,
    height=20,
    font=("Arial", 18),
    fg="white",
    bg="black"
)
output_text.pack(pady=10)
output_text.insert(tk.END, "Press '-' to translate.\n")

def set_output(text):
    """Immediately set the output text."""
    output_text.delete('1.0', tk.END)
    output_text.insert(tk.END, text + "\n")
    output_text.see(tk.END)

def animate_text(text, delay=200):
    """
    Animate the given text by displaying one word at a time.
    
    :param text: Full text to animate.
    :param delay: Delay (in milliseconds) between words.
    """
    words = text.split()
    output_text.delete('1.0', tk.END)  # Clear any existing text
    
    def update_word(index, current_text=""):
        if index < len(words):
            current_text += words[index] + " "
            output_text.delete('1.0', tk.END)
            output_text.insert(tk.END, current_text)
            output_text.see(tk.END)
            root.after(delay, update_word, index+1, current_text)
    
    update_word(0, "")

def process_audio():
    while True:
        # Read an audio chunk from the stream and append it to the buffer
        data = stream.read(CHUNK, exception_on_overflow=False)
        audio_buffer.append(data)

        # Check for key press to trigger translation
        if keyboard.is_pressed('-'):
            timestamp = int(time.time())
            filename = f"clip_{timestamp}.wav"
            
            # Write the current audio buffer to a WAV file
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(p.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                for chunk_data in audio_buffer:
                    wf.writeframes(chunk_data)
            
            # Show loading status in the GUI
            root.after(0, lambda: set_output("Loading..."))
            
            try:
                with open(filename, 'rb') as f:
                    files = {'file': f}
                    data_payload = {
                        "source_language": "sv",
                        "target_language": "en"
                    }
                    response = requests.post(endpoint_url, files=files, data=data_payload)
                    
                    if response.status_code == 200:
                        translation_data = response.json()
                        if 'translation' in translation_data:
                            translation_text = translation_data['translation']
                            # Animate the translation so it appears word-by-word
                            root.after(0, lambda: animate_text(translation_text, delay=200))
                        else:
                            root.after(0, lambda: set_output("Error: 'translation' not found in response:\n" + str(translation_data)))
                    else:
                        root.after(0, lambda: set_output("Error sending file. Status code: " + str(response.status_code)))
            except Exception as e:
                root.after(0, lambda: set_output("Error sending file: " + str(e)))
            
            os.remove(filename)
            time.sleep(1)  # Debounce key press

        # Press 'q' to exit
        if keyboard.is_pressed('q'):
            root.after(0, lambda: set_output("Exiting..."))
            break

def run_audio_thread():
    audio_thread = threading.Thread(target=process_audio, daemon=True)
    audio_thread.start()

run_audio_thread()
root.mainloop()

# Cleanup
stream.stop_stream()
stream.close()
p.terminate()
