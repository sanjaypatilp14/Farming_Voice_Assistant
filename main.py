"""Main file for the Jarvis project"""
import os
from os import PathLike
from time import time
import asyncio
from typing import Union
from dotenv import load_dotenv
from google import genai
from deepgram import Deepgram
import pygame
from pygame import mixer
import elevenlabs
from record import speech_to_text

# Load API keys
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
elevenlabs.set_api_key(os.getenv("ELEVENLABS_API_KEY"))

# Initialize APIs
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
chat = gemini_client.chats.create(model="gemini-2.5-flash")
deepgram = Deepgram(DEEPGRAM_API_KEY)
# mixer is a pygame module for playing audio
mixer.init()

# Change the context if you want to change Jarvis' personality
context = "You are the Farming Voice Assistant. Keep replies to 1–2 short sentences."
conversation = {"Conversation": []}
RECORDING_PATH = "audio/recording.wav"

def request_gpt(prompt: str) -> str:
    import time as _t
    delays = [0.5, 1, 2, 4, 8]  # exponential backoff
    for d in delays:
        try:
            resp = chat.send_message(prompt)
            return resp.text
        except Exception as e:
            # Retry on transient overloads
            if "UNAVAILABLE" in str(e) or "503" in str(e):
                _t.sleep(d)
                continue
            # Non-retryable error: surface it
            raise
    # One final attempt after backoff
    resp = chat.send_message(prompt)
    return resp.text

async def transcribe(
    file_name: Union[Union[str, bytes, PathLike[str], PathLike[bytes]], int]
):
    """
    Transcribe audio using Deepgram API.
    Args:
        - file_name: The name of the file to transcribe.
    Returns:
        The response from the API.
    """
    with open(file_name, "rb") as audio:
        source = {"buffer": audio, "mimetype": "audio/wav"}
        response = await deepgram.transcription.prerecorded(source)
        return response["results"]["channels"][0]["alternatives"][0]["words"]

def log(log: str):
    """
    Print and write to status.txt
    """
    print(log)
    with open("status.txt", "w") as f:
        f.write(log)

if __name__ == "__main__":
    while True:
        # Record audio
        log("Listening...")
        speech_to_text()
        log("Done listening")

        # Transcribe audio
        current_time = time()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        words = loop.run_until_complete(transcribe(RECORDING_PATH))
        string_words = " ".join(
            word_dict.get("word") for word_dict in words if "word" in word_dict
        )
        with open("conv.txt", "a") as f:
            f.write(f"{string_words}\n")
        transcription_time = time() - current_time
        log(f"Finished transcribing in {transcription_time:.2f} seconds.")

        # Get response from GPT-3
        current_time = time()
        context +=  f"\nUser: {string_words}\nAssistant: "
        response = request_gpt(context)
        context += response
        gpt_time = time() - current_time
        log(f"Finished generating response in {gpt_time:.2f} seconds.")

        # Convert response to audio
        current_time = time()
        audio = elevenlabs.generate(
            text=response, voice="iWNf11sz1GrUE4ppxTOL", model="eleven_monolingual_v1"
        )
        elevenlabs.save(audio, "audio/response.wav")
        audio_time = time() - current_time
        log(f"Finished generating audio in {audio_time:.2f} seconds.")

        # Play response
        log("Speaking...")
        sound = mixer.Sound("audio/response.wav")
        # Add response as a new line to conv.txt
        with open("conv.txt", "a") as f:
            f.write(f"{response}\n")
        sound.play()
        pygame.time.wait(int(sound.get_length() * 1000))
        print(f"\n --- USER: {string_words}\n --- JARVIS: {response}\n")
