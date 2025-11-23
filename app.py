import streamlit as st
import requests
from audio_recorder_streamlit import audio_recorder
import base64
from io import BytesIO

# Page config
st.set_page_config(page_title="AI Voice Bot", page_icon="🎤", layout="wide")

# API URL
API_URL = "https://voice-assistant-1-55qh.onrender.com"

# Initialize session state
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processing" not in st.session_state:
    st.session_state.processing = False
if "last_audio_bytes" not in st.session_state:
    st.session_state.last_audio_bytes = None

def speech_to_text(audio_bytes):
    """Convert speech to text via API"""
    try:
        files = {"audio": ("audio.wav", audio_bytes, "audio/wav")}
        response = requests.post(f"{API_URL}/speech-to-text", files=files, timeout=30)
        if response.status_code == 200:
            return response.json()["transcript"]
        else:
            st.error(f"Speech-to-text error: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

def get_ai_response(message):
    """Get AI response via API"""
    try:
        data = {
            "message": message,
            "conversation_history": st.session_state.conversation_history[-10:]  # Last 10 messages
        }
        response = requests.post(f"{API_URL}/chat", json=data, timeout=30)
        if response.status_code == 200:
            return response.json()["response"]
        else:
            st.error(f"Chat error: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

def text_to_speech(text):
    """Convert text to speech via API"""
    try:
        data = {"text": text}
        response = requests.post(f"{API_URL}/text-to-speech", json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            audio_bytes = base64.b64decode(result["audio"])
            return audio_bytes
        else:
            st.error(f"Text-to-speech error: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

def autoplay_audio(audio_bytes):
    """Autoplay audio in Streamlit"""
    try:
        b64 = base64.b64encode(audio_bytes).decode()
        audio_html = f"""
            <audio id="audio_player" autoplay>
                <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            <script>
                var audio = document.getElementById('audio_player');
                audio.play().catch(function(error) {{
                    console.log('Autoplay failed:', error);
                }});
            </script>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Audio playback error: {str(e)}")

# UI
st.markdown("# **Krishna Ghetia Voice Bot**")
st.title("🎤 AI Voice Bot")
st.markdown("### Talk to AI - Speak or Type!")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("---")
    
    st.markdown("**Features:**")
    st.markdown("🎙️ Voice Input")
    st.markdown("💬 Text Chat")
    st.markdown("🔊 Voice Output")
    st.markdown("📝 Conversation History")
    
    st.markdown("---")
    
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.conversation_history = []
        st.session_state.messages = []
        st.session_state.processing = False
        st.session_state.last_audio_bytes = None
        st.rerun()
    
    st.markdown("---")
    st.markdown("**Status:**")
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
        if response.status_code == 200:
            st.success("✅ Backend Connected")
            data = response.json()
            if data.get("deepgram_connected"):
                st.success("✅ Deepgram Connected")
            if data.get("groq_connected"):
                st.success("✅ Groq Connected")
        else:
            st.error("❌ Backend Error")
    except:
        st.error("❌ Backend Offline")
        st.info("Make sure to run: python main.py")

# Main chat interface
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("💬 Conversation")
    
    # Display chat messages
    chat_container = st.container(height=400)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant" and "audio" in msg:
                    st.audio(msg["audio"], format="audio/mp3")

with col2:
    st.subheader("🎙️ Voice Input")
    
    # Only show recorder if not processing
    if not st.session_state.processing:
        audio_bytes = audio_recorder(
            text="Click to record",
            recording_color="#e74c3c",
            neutral_color="#3498db",
            icon_size="2x",
            key="audio_recorder"
        )
    else:
        st.info("Processing... Please wait")
        audio_bytes = None

# Voice input processing
if audio_bytes and not st.session_state.processing:
    # Check if this is a new recording (different from last one)
    if st.session_state.last_audio_bytes != audio_bytes:
        st.session_state.last_audio_bytes = audio_bytes
        st.session_state.processing = True
        
        with st.spinner("🎧 Processing voice..."):
            transcript = speech_to_text(audio_bytes)
            
            if transcript and transcript.strip():
                st.success(f"✅ You said: {transcript}")
                
                # Add user message
                st.session_state.messages.append({"role": "user", "content": transcript})
                st.session_state.conversation_history.append({"role": "user", "content": transcript})
                
                # Get AI response
                with st.spinner("🤔 Thinking..."):
                    ai_response = get_ai_response(transcript)
                    
                    if ai_response and ai_response.strip():
                        # Generate speech
                        with st.spinner("🔊 Generating speech..."):
                            audio_data = text_to_speech(ai_response)
                            
                            if audio_data:
                                # Add assistant message
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": ai_response,
                                    "audio": audio_data
                                })
                                st.session_state.conversation_history.append({
                                    "role": "assistant",
                                    "content": ai_response
                                })
                                
                                st.success("✅ Response generated!")
                                
                                # Autoplay the response
                                autoplay_audio(audio_data)
                                
                                # Reset processing state
                                st.session_state.processing = False
                                st.rerun()
                            else:
                                st.error("Failed to generate speech audio")
                                st.session_state.processing = False
                    else:
                        st.error("Failed to get AI response")
                        st.session_state.processing = False
            else:
                st.warning("No speech detected. Please try again.")
                st.session_state.processing = False
                st.session_state.last_audio_bytes = None

# Text input
if not st.session_state.processing:
    user_input = st.chat_input("Or type your message here...")
else:
    user_input = None
    st.info("⏳ Processing voice input... Text input disabled temporarily")

if user_input:
    st.session_state.processing = True
    
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.conversation_history.append({"role": "user", "content": user_input})
    
    # Get AI response
    with st.spinner("🤔 Thinking..."):
        ai_response = get_ai_response(user_input)
        
        if ai_response and ai_response.strip():
            # Generate speech
            with st.spinner("🔊 Generating speech..."):
                audio_data = text_to_speech(ai_response)
                
                if audio_data:
                    # Add assistant message
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": ai_response,
                        "audio": audio_data
                    })
                    st.session_state.conversation_history.append({
                        "role": "assistant",
                        "content": ai_response
                    })
                    
                    st.success("✅ Response generated!")
                    
                    # Autoplay the response
                    autoplay_audio(audio_data)
                    
                    # Reset processing state
                    st.session_state.processing = False
                    st.rerun()
                else:
                    st.error("Failed to generate speech audio")
                    st.session_state.processing = False
        else:
            st.error("Failed to get AI response")
            st.session_state.processing = False

# Footer
st.markdown("---")
st.markdown("Made with ❤️ using Streamlit, FastAPI, Deepgram & Groq")
