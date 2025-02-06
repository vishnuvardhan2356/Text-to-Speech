import streamlit as st
from pymongo import MongoClient
from urllib.parse import quote_plus
import requests
import uuid
import os
import base64
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
import datetime
import wave
import io
import azure.cognitiveservices.speech as speechsdk
import time
import pandas as pd

# MongoDB configuration
username = quote_plus("vishnub")
password = quote_plus("Vishnu1234")
connection_string = f'mongodb+srv://{username}:{password}@tts.qf7rw.mongodb.net/tts_history_db'
client = MongoClient(connection_string)
db = client["tts_history_db"]
collection = db["history"]

# API Keys
PLAY_AI_API_KEY = 'ak-8ed129b1621347858f25f3be20c05466'
ELEVENLABS_API_KEY = 'sk_6b37b815e99f6442a1f2f5a11a2fb2484ad986afafb10472'
SARVAM_API_KEY = 'c4944e8a-8d1a-4e5c-bbcb-d5069a7f34c6'
AZURE_SPEECH_KEY = "6CVqzWbDeAHx3XIWQ1amYsNFAbPX8VZUQ4mJ66xcuztqhgGbydqsJQQJ99AKACGhslBXJ3w3AAAYACOGJLNq"
AZURE_REGION = "centralindia"
AZURE_CUSTOM_VOICE_DEPLOYMENT_ID = "ac6aadae-aef9-4e54-a198-9302daf23430"
# RESEMBLE_API_KEY = 'api key'  # Commented out Resemble
CARTESIA_API_KEY = 'sk_car_jq004Gx10Yk35O33qW5wV'


# Initialize ElevenLabs client
eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# Timing Metrics Class
class TimingMetrics:
    def __init__(self):
        self.start_time = None
        self.first_byte_time = None
        self.end_time = None

    def start(self):
        self.start_time = time.time()

    def mark_first_byte(self):
        if not self.first_byte_time:
            self.first_byte_time = time.time()

    def end(self):
        self.end_time = time.time()

    def get_metrics(self):
        if not all([self.start_time, self.first_byte_time, self.end_time]):
            return None
        
        ttfb = self.first_byte_time - self.start_time
        total_time = self.end_time - self.start_time
        return {
            "time_to_first_byte": round(ttfb, 3),
            "total_response_time": round(total_time, 3)
        }

def text_to_speech_playai(text):
    metrics = TimingMetrics()
    metrics.start()
    
    url = "https://api.play.ai/api/v1/tts/stream"
    headers = {
        "AUTHORIZATION": PLAY_AI_API_KEY,
        "X-USER-ID": 'gETymo585oUyMMNisi9I2DQX7Q83',
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "PlayDialog",
        "text": text,
        "voice": "s3://voice-cloning-zero-shot/bc3aac42-8e8f-43e2-8919-540f817a0ac4/original/manifest.json",
        "outputFormat": "mp3",
        "speed": 1.0,
        "sampleRate": 48000,
        "seed": None,
        "temperature": 0.7,
        "language": "english"
    }
    
    response = requests.post(url, json=payload, headers=headers, stream=True)
    
    if response.status_code == 200:
        metrics.mark_first_byte()
        save_file_path = f"playai_{uuid.uuid4()}.mp3"
        audio_data = b''
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                audio_data += chunk
        
        with open(save_file_path, "wb") as f:
            f.write(audio_data)
            
        metrics.end()
        return save_file_path, audio_data, metrics.get_metrics()
    else:
        raise Exception(f"Play.ai API error: {response.status_code} - {response.text}")

def text_to_speech_elevenlabs(text):
    metrics = TimingMetrics()
    metrics.start()
    
    response = eleven_client.text_to_speech.convert(
        voice_id="fB7yp9cWTRBT9Taud6m9",
        output_format="mp3_22050_32",
        text=text,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=0.5,
            style=0.0,
            use_speaker_boost=True,
        ),
    )

    save_file_path = f"elevenlabs_{uuid.uuid4()}.mp3"
    audio_data = b''
    first_chunk = True
    
    for chunk in response:
        if chunk:
            if first_chunk:
                metrics.mark_first_byte()
                first_chunk = False
            audio_data += chunk
    
    with open(save_file_path, "wb") as f:
        f.write(audio_data)
        
    metrics.end()
    return save_file_path, audio_data, metrics.get_metrics()


def text_to_speech_sarvam(text):
    metrics = TimingMetrics()
    metrics.start()
    
    url = "https://api.sarvam.ai/text-to-speech"
    payload = {
        "target_language_code": "en-IN",
        "inputs": [text],
        "speaker": "meera"
    }
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.request("POST", url, json=payload, headers=headers)
    metrics.mark_first_byte()

    if response.status_code == 200:
        response_json = response.json()
        
        if "audios" not in response_json or not response_json["audios"]:
            raise Exception("No audio data received from Sarvam API.")

        base64_audio = response_json["audios"][0]
        audio_data = base64.b64decode(base64_audio)

        save_file_path = f"sarvam_{uuid.uuid4()}.wav"
        with open(save_file_path, "wb") as f:
            f.write(audio_data)
            
        metrics.end()
        return save_file_path, audio_data, metrics.get_metrics()
    else:
        raise Exception(f"Sarvam API error: {response.status_code} - {response.text}")

def text_to_speech_azure(text, use_custom_voice=False):
    metrics = TimingMetrics()
    metrics.start()
    
    try:
        if use_custom_voice:
            speech_config = speechsdk.SpeechConfig(
                subscription=AZURE_SPEECH_KEY, 
                region=AZURE_REGION
            )
            speech_config.endpoint_id = AZURE_CUSTOM_VOICE_DEPLOYMENT_ID
            
            file_name = f"azure_custom_{uuid.uuid4()}.wav"
            audio_config = speechsdk.audio.AudioOutputConfig(filename=file_name)
            
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config, 
                audio_config=audio_config
            )
            
            metrics.mark_first_byte()
            result = speech_synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                with open(file_name, 'rb') as audio_file:
                    audio_data = audio_file.read()
                metrics.end()
                return file_name, audio_data, metrics.get_metrics()
            else:
                raise Exception("Speech synthesis failed")
        else:
            speech_config = speechsdk.SpeechConfig(
                subscription=AZURE_SPEECH_KEY, 
                region=AZURE_REGION
            )
            
            file_name = f"azure_standard_{uuid.uuid4()}.wav"
            audio_config = speechsdk.audio.AudioOutputConfig(filename=file_name)
            
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config, 
                audio_config=audio_config
            )
            
            metrics.mark_first_byte()
            result = speech_synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                with open(file_name, 'rb') as audio_file:
                    audio_data = audio_file.read()
                metrics.end()
                return file_name, audio_data, metrics.get_metrics()
            else:
                raise Exception("Speech synthesis failed")
    except Exception as e:
        raise Exception(f"Azure TTS error: {str(e)}")

def text_to_speech_cartesia(text):
    metrics = TimingMetrics()
    metrics.start()
    
    try:
        url = "https://api.cartesia.ai/tts/bytes"
        headers = {
            "Cartesia-Version": "2024-06-10",
            "X-API-Key": CARTESIA_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "model_id": "sonic-english",
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": "faf0731e-dfb9-4cfc-8119-259a79b27e12"
            },
            "output_format": {
                "container": "mp3",
                "bit_rate": 128000,
                "sample_rate": 44100
            },
            "language": "en"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        metrics.mark_first_byte()
        
        if response.status_code == 200:
            save_file_path = f"cartesia_{uuid.uuid4()}.mp3"
            with open(save_file_path, "wb") as f:
                f.write(response.content)
            metrics.end()
            return save_file_path, response.content, metrics.get_metrics()
        else:
            raise Exception(f"API request failed with status code: {response.status_code}")
            
    except Exception as e:
        raise Exception(f"Cartesia API error: {str(e)}")

def cleanup_old_files():
    try:
        current_dir = os.getcwd()
        for file in os.listdir(current_dir):
            if any(file.startswith(prefix) for prefix in ['playai_', 'elevenlabs_', 'sarvam_', 'azure_', 'cartesia_']) and \
               file.endswith(('.mp3', '.wav')):
                file_path = os.path.join(current_dir, file)
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error removing file {file}: {str(e)}")
    except Exception as e:
        print(f"Error in cleanup: {str(e)}")

# Streamlit UI
st.title("TTS Service Evaluator")

text_input = st.text_area("Enter text to convert to speech")

if st.button("Generate Speech"):
    if text_input:
        results = {}
        timing_results = {}
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Generate all audio
            services = {
                "Play.ai": (text_to_speech_playai, "mp3"),
                "Eleven Labs": (text_to_speech_elevenlabs, "mp3"),
                "Sarvam": (text_to_speech_sarvam, "wav"),
                "Cartesia": (text_to_speech_cartesia, "mp3"),
                "Azure Standard": (lambda x: text_to_speech_azure(x, False), "wav"),
                "Azure Custom": (lambda x: text_to_speech_azure(x, True), "wav")
            }
            
            progress_step = 100 / len(services)
            current_progress = 0
            
            for service_name, (func, format_type) in services.items():
                status_text.text(f"Generating {service_name} audio...")
                path, audio, metrics = func(text_input)
                results[service_name] = {"path": path, "audio": audio, "format": format_type}
                timing_results[service_name] = metrics
                current_progress += progress_step
                progress_bar.progress(int(current_progress))
            
            # Create timing comparison DataFrame
            timing_data = {
                'Service': [],
                'Time to First Byte (s)': [],
                'Total Response Time (s)': []
            }
            
            for service, metrics in timing_results.items():
                timing_data['Service'].append(service)
                timing_data['Time to First Byte (s)'].append(metrics['time_to_first_byte'])
                timing_data['Total Response Time (s)'].append(metrics['total_response_time'])
            
            df = pd.DataFrame(timing_data)
            
            # Display timing comparison
            st.subheader("Timing Comparison")
            st.dataframe(df)
            
            # Display audio results
            st.subheader("Generated Audio")
            for service_name, data in results.items():
                st.write(f"**{service_name}**")
                st.audio(data["audio"], format=f"audio/{data['format']}")
                metrics = timing_results[service_name]
                st.write(f"⏱️ Time to First Byte: {metrics['time_to_first_byte']}s")
                st.write(f"⌛ Total Response Time: {metrics['total_response_time']}s")
                st.divider()
            
        except Exception as e:
            st.error(f"Error generating audio: {str(e)}")
        finally:
            progress_bar.empty()
            status_text.empty()
            cleanup_old_files()
    else:
        st.error("Please enter text to convert.")

# Run cleanup when the app starts
cleanup_old_files()