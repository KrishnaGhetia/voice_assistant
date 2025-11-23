from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import base64
import tempfile
from dotenv import load_dotenv
from deepgram import DeepgramClient, PrerecordedOptions, SpeakOptions
from groq import Groq
import uvicorn

# Load environment variables
load_dotenv()

# Get API keys from environment variables
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print(f"🔑 Deepgram Key Loaded: {bool(DEEPGRAM_API_KEY)} (Length: {len(DEEPGRAM_API_KEY) if DEEPGRAM_API_KEY else 0})")
print(f"🔑 Groq Key Loaded: {bool(GROQ_API_KEY)} (Length: {len(GROQ_API_KEY) if GROQ_API_KEY else 0})")

if not DEEPGRAM_API_KEY:
    raise RuntimeError("❌ DEEPGRAM_API_KEY not set in .env file!")
if not GROQ_API_KEY:
    raise RuntimeError("❌ GROQ_API_KEY not set in .env file!")

# Initialize clients
dg_client = DeepgramClient(DEEPGRAM_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Voice Bot API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TextRequest(BaseModel):
    text: str

class ChatRequest(BaseModel):
    message: str
    conversation_history: list = []


@app.get("/")
async def root():
    return {
        "message": "Voice Bot API is running",
        "deepgram_connected": bool(DEEPGRAM_API_KEY),
        "groq_connected": bool(GROQ_API_KEY)
    }


@app.post("/speech-to-text")
async def speech_to_text_endpoint(audio: UploadFile = File(...)):
    """Convert speech to text using Deepgram"""
    try:
        audio_data = await audio.read()
        
        # Deepgram SDK v3 options
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
        )
        
        # Transcribe
        response = dg_client.listen.prerecorded.v("1").transcribe_file(
            {"buffer": audio_data},
            options
        )
        
        transcript = response.results.channels[0].alternatives[0].transcript
        
        print(f"✅ Transcribed: {transcript}")
        return {"transcript": transcript, "success": True}
    
    except Exception as e:
        print(f"❌ Speech-to-text error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/chat")
async def chat(request: ChatRequest):
    """Get AI response using Groq"""
    try:
        # Limit conversation history to last 6 messages to prevent repetition
        recent_history = request.conversation_history[-6:] if len(request.conversation_history) > 6 else request.conversation_history
        
        messages = [
            {"role": "system", "content": "You are a helpful voice assistant. Give short, direct answers in 2-3 sentences maximum. Never repeat yourself."}
        ]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": request.message})
        
        print(f"💬 User: {request.message}")
        
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=150,  # Reduced to keep answers short
            top_p=0.9,
            frequency_penalty=0.5,  # Prevent repetition
            presence_penalty=0.3
        )
        
        ai_response = completion.choices[0].message.content
        
        print(f"🤖 AI: {ai_response}")
        return {"response": ai_response, "success": True}
    
    except Exception as e:
        print(f"❌ Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/text-to-speech")
async def text_to_speech_endpoint(request: TextRequest):
    """Convert text to speech using Deepgram"""
    try:
        print(f"🔊 Converting to speech: {request.text[:50]}...")
        
        SPEAK_OPTIONS = {"text": request.text}
        
        # Use temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            filename = tmp_file.name
        
        options = SpeakOptions(
            model="aura-asteria-en",
        )
        
        response = dg_client.speak.v("1").save(filename, SPEAK_OPTIONS, options)
        
        # Read the generated file
        with open(filename, "rb") as f:
            audio_bytes = f.read()
        
        # Clean up
        if os.path.exists(filename):
            os.remove(filename)
        
        print(f"✅ Audio generated: {len(audio_bytes)} bytes")
        
        # Return base64 encoded audio
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        return {
            "audio": audio_base64,
            "mime_type": "audio/mpeg",
            "success": True
        }
    
    except Exception as e:
        print(f"❌ Text-to-speech error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/voice")
async def voice_bot(file: UploadFile = File(...)):
    """Complete voice bot pipeline: Speech → Text → AI → Speech"""
    try:
        print("🎤 Voice bot request received")
        
        # 1. Read uploaded audio
        audio_bytes = await file.read()
        print(f"📥 Audio received: {len(audio_bytes)} bytes")
        
        # 2. Speech to Text
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
        )
        
        stt_response = dg_client.listen.prerecorded.v("1").transcribe_file(
            {"buffer": audio_bytes},
            options
        )
        
        user_text = stt_response.results.channels[0].alternatives[0].transcript
        print(f"✅ Transcribed: {user_text}")
        
        # 3. Get AI response
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful voice assistant. Give short, direct answers in 2-3 sentences. Never repeat yourself."},
                {"role": "user", "content": user_text}
            ],
            temperature=0.7,
            max_tokens=150,
            frequency_penalty=0.5,
            presence_penalty=0.3
        )
        
        bot_text = completion.choices[0].message.content
        print(f"🤖 AI Response: {bot_text}")
        
        # 4. Text to Speech
        SPEAK_OPTIONS = {"text": bot_text}
        
        # Use temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            filename = tmp_file.name
        
        tts_options = SpeakOptions(
            model="aura-asteria-en",
        )
        
        tts_response = dg_client.speak.v("1").save(filename, SPEAK_OPTIONS, tts_options)
        
        # Read the generated file
        with open(filename, "rb") as f:
            bot_audio_bytes = f.read()
        
        # Clean up
        if os.path.exists(filename):
            os.remove(filename)
        
        print(f"✅ Audio generated: {len(bot_audio_bytes)} bytes")
        
        # 5. Return everything
        return {
            "user_text": user_text,
            "bot_text": bot_text,
            "bot_audio": base64.b64encode(bot_audio_bytes).decode("utf-8"),
            "audio_mime": "audio/mpeg",
            "success": True
        }
    
    except Exception as e:
        print(f"❌ Voice bot error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/test-tts")
async def test_tts():
    """Test endpoint for TTS"""
    try:
        SPEAK_OPTIONS = {"text": "Hello, this is a test message."}
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            filename = tmp_file.name
        
        options = SpeakOptions(model="aura-asteria-en")
        response = dg_client.speak.v("1").save(filename, SPEAK_OPTIONS, options)
        
        with open(filename, "rb") as f:
            audio = f.read()
        
        os.remove(filename)
        
        return {"success": True, "audio_size": len(audio)}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8888))
    print(f"🚀 Starting Voice Bot API on http://0.0.0.0:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
