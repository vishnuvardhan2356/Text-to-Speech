# imports
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
# from resemble import Resemble  # Commented out Resemble

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

def text_to_speech_playai(text):
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
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        save_file_path = f"playai_{uuid.uuid4()}.mp3"
        with open(save_file_path, "wb") as f:
            f.write(response.content)
        return save_file_path, response.content
    else:
        raise Exception(f"Play.ai API error: {response.status_code} - {response.text}")

def text_to_speech_elevenlabs(text):
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
    for chunk in response:
        if chunk:
            audio_data += chunk
    
    with open(save_file_path, "wb") as f:
        f.write(audio_data)
    return save_file_path, audio_data

def text_to_speech_sarvam(text):
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

    if response.status_code == 200:
        response_json = response.json()
        
        if "audios" not in response_json or not response_json["audios"]:
            raise Exception("No audio data received from Sarvam API.")

        base64_audio = response_json["audios"][0]
        audio_data = base64.b64decode(base64_audio)

        save_file_path = f"sarvam_{uuid.uuid4()}.wav"
        with open(save_file_path, "wb") as f:
            f.write(audio_data)
        return save_file_path, audio_data
    else:
        raise Exception(f"Sarvam API error: {response.status_code} - {response.text}")

def text_to_speech_azure(text, use_custom_voice=False):
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
            
            result = speech_synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                with open(file_name, 'rb') as audio_file:
                    audio_data = audio_file.read()
                return file_name, audio_data
            else:
                if result.reason == speechsdk.ResultReason.Canceled:
                    cancellation_details = result.cancellation_details
                    raise Exception(f"Speech synthesis canceled: {cancellation_details.reason}")
                raise Exception("Speech synthesis failed")
            
        else:
            token_url = f'https://{AZURE_REGION}.api.cognitive.microsoft.com/sts/v1.0/issueToken'
            token_headers = {
                'Ocp-Apim-Subscription-Key': AZURE_SPEECH_KEY
            }
            token_response = requests.post(token_url, headers=token_headers)
            
            if token_response.status_code != 200:
                raise Exception("Failed to get access token")
                
            access_token = token_response.text

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/ssml+xml',
                'X-Microsoft-OutputFormat': 'riff-24khz-16bit-mono-pcm',
                'User-Agent': 'TTS Service Evaluator'
            }

            url = f'https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1'
            
            ssml = f"""
            <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>
                <voice name='en-IN-NeerjaNeural'>
                    <prosody rate="medium">
                        {text}
                    </prosody>
                </voice>
            </speak>
            """

            response = requests.post(url, headers=headers, data=ssml.encode('utf-8'))

            if response.status_code == 200:
                save_file_path = f"azure_standard_{uuid.uuid4()}.wav"
                with open(save_file_path, "wb") as f:
                    f.write(response.content)
                return save_file_path, response.content
            else:
                raise Exception(f"Azure TTS API error: {response.status_code} - {response.text}")

    except Exception as e:
        raise Exception(f"Error in Azure TTS: {str(e)}")

def text_to_speech_cartesia(text):
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
        
        if response.status_code == 200:
            save_file_path = f"cartesia_{uuid.uuid4()}.mp3"
            with open(save_file_path, "wb") as f:
                f.write(response.content)
            return save_file_path, response.content
        else:
            raise Exception(f"API request failed with status code: {response.status_code}, Response: {response.text}")
            
    except Exception as e:
        raise Exception(f"Cartesia API error: {str(e)}")

def save_to_history(text, results):
    history_entry = {
        "text": text,
        "results": results,
        "timestamp": datetime.datetime.now()
    }
    collection.insert_one(history_entry)

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
        if os.path.exists('temp.wav'):
            os.remove('temp.wav')
    except Exception as e:
        print(f"Error in cleanup: {str(e)}")

# Streamlit UI
# Streamlit UI
st.title("TTS Service Evaluator")

text_input = st.text_area("Enter text to convert to speech")

if st.button("Generate Speech"):
    if text_input:
        results = {}
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Generate Play.ai audio
            status_text.text("Generating Play.ai audio...")
            progress_bar.progress(16)
            playai_path, playai_audio = text_to_speech_playai(text_input)
            results["Play.ai"] = {"path": playai_path, "audio": playai_audio}
            
            # Generate Eleven Labs audio
            status_text.text("Generating Eleven Labs audio...")
            progress_bar.progress(32)
            elevenlabs_path, elevenlabs_audio = text_to_speech_elevenlabs(text_input)
            results["Eleven Labs"] = {"path": elevenlabs_path, "audio": elevenlabs_audio}
            
            # Generate Sarvam audio
            status_text.text("Generating Sarvam audio...")
            progress_bar.progress(48)
            sarvam_path, sarvam_audio = text_to_speech_sarvam(text_input)
            results["Sarvam"] = {"path": sarvam_path, "audio": sarvam_audio}
            
            # Generate Cartesia audio
            status_text.text("Generating Cartesia audio...")
            progress_bar.progress(64)
            cartesia_path, cartesia_audio = text_to_speech_cartesia(text_input)
            results["Cartesia"] = {"path": cartesia_path, "audio": cartesia_audio}
            
            # Generate Azure Standard audio
            status_text.text("Generating Azure Standard Voice audio...")
            progress_bar.progress(80)
            azure_path, azure_audio = text_to_speech_azure(text_input, use_custom_voice=False)
            results["Azure Standard"] = {"path": azure_path, "audio": azure_audio}
            
            # Generate Azure Custom Voice audio
            status_text.text("Generating Azure Custom Voice audio...")
            progress_bar.progress(90)
            azure_custom_path, azure_custom_audio = text_to_speech_azure(text_input, use_custom_voice=True)
            results["Azure Custom"] = {"path": azure_custom_path, "audio": azure_custom_audio}
            
            progress_bar.progress(100)
            status_text.text("All audio generated successfully!")
            
            # Display results
            st.subheader("Generated Audio")
            
            # Play.ai Row
            st.write("Play.ai")
            st.audio(results["Play.ai"]["audio"], format="audio/mp3")
            st.divider()
            
            # Eleven Labs Row
            st.write("Eleven Labs")
            st.audio(results["Eleven Labs"]["audio"], format="audio/mp3")
            st.divider()
            
            # Sarvam Row
            st.write("Sarvam")
            st.audio(results["Sarvam"]["audio"], format="audio/wav")
            st.divider()
            
            # Cartesia Row
            st.write("Cartesia")
            st.audio(results["Cartesia"]["audio"], format="audio/mp3")
            st.divider()
            
            # Azure Standard Row
            st.write("Azure Standard")
            st.audio(results["Azure Standard"]["audio"], format="audio/wav")
            st.divider()
            
            # Azure Custom Row (always included now)
            st.write("Azure Custom")
            st.audio(results["Azure Custom"]["audio"], format="audio/wav")
            st.divider()
            
            # Save to history
            save_to_history(text_input, results)
            
        except Exception as e:
            st.error(f"Error generating audio: {str(e)}")
            
        finally:
            progress_bar.empty()
            status_text.empty()
    else:
        st.error("Please enter text to convert.")

if st.button("Show History"):
    entries = collection.find().sort("timestamp", -1)
    for entry in entries:
        st.write(f"Text: {entry.get('text', 'No text available')}")
        st.write(f"Generated at: {entry.get('timestamp', 'Time not available')}")
        st.write("Generated Audio:")
        
        if 'results' in entry and isinstance(entry['results'], dict):
            for service_name, service_data in entry['results'].items():
                st.write(service_name)
                try:
                    format_type = 'audio/mp3' if 'mp3' in service_data["path"] else 'audio/wav'
                    st.audio(service_data["audio"], format=format_type)
                except Exception as e:
                    st.error(f"Error playing {service_name} audio: {str(e)}")
                st.divider()
        else:
            st.error("Invalid history entry format")
            
        st.markdown("---")

# Run cleanup when the app starts
cleanup_old_files()