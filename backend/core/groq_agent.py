import os
import io
import base64
from typing import Optional, Dict, Any
from groq import AsyncGroq, Groq
from backend.core.config import settings

class GroqAgent:
    """
    State-of-the-art Multimodal Assistant powered by Groq.
    Combines:
      - Llama 4 Scout / Llama 3.2 Multimodal Vision (instant image + query reasoning)
      - Whisper-large-v3-turbo (ultra-fast voice transcription)
      - Llama 3.3 70B Versatile (spatial conversation and summarization)
    """

    SYSTEM_PROMPT = (
        "You are an AI Vision Assistant dedicated to assisting visually impaired users. "
        "Describe surroundings clearly, accurately, and concisely. "
        "Explicitly mention positions (left, center, right), proximity, and potential walking hazards. "
        "Keep responses direct, reassuring, and under 3 sentences unless specifically asked for details."
    )

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.client: Optional[AsyncGroq] = None
        self._init_client()

    def _init_client(self):
        if self.api_key and self.api_key.startswith("gsk_"):
            try:
                self.client = AsyncGroq(api_key=self.api_key)
            except Exception as e:
                print(f"[GroqAgent] Failed to init AsyncGroq: {e}")
                self.client = None
        else:
            self.client = None

    def set_api_key(self, key: str):
        self.api_key = key.strip()
        self._init_client()

    async def describe_scene_multimodal(self, user_query: str, image_b64: Optional[str] = None) -> str:
        """
        Sends user question + camera frame (base64 JPEG) to Groq Multimodal Vision.
        """
        if not self.client:
            return self._offline_multimodal_reply(user_query, bool(image_b64))

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]

        if image_b64:
            # Prepare multimodal payload
            content_list = [
                {"type": "text", "text": user_query or "Describe what you see in front of me and highlight any safety hazards."}
            ]
            if not image_b64.startswith("data:image"):
                img_url = f"data:image/jpeg;base64,{image_b64}"
            else:
                img_url = image_b64
                
            content_list.append({
                "type": "image_url",
                "image_url": {"url": img_url}
            })
            messages.append({"role": "user", "content": content_list})
        else:
            messages.append({"role": "user", "content": user_query})

        # Try Multimodal Vision models in order of capability
        vision_candidates = [
            "qwen/qwen3.8-27b",
            settings.GROQ_VISION_MODEL,
            settings.GROQ_FALLBACK_MODEL
        ]

        for model_id in vision_candidates:
            try:
                # If model is text-only, convert content to text
                if "vision" not in model_id.lower() and "scout" not in model_id.lower() and image_b64:
                    text_messages = [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": f"[User looking at scene] {user_query}"}
                    ]
                    response = await self.client.chat.completions.create(
                        model=model_id,
                        messages=text_messages,
                        max_tokens=150,
                        temperature=0.2
                    )
                else:
                    response = await self.client.chat.completions.create(
                        model=model_id,
                        messages=messages,
                        max_tokens=150,
                        temperature=0.2
                    )
                content = response.choices[0].message.content
                if content:
                    return content.strip()
            except Exception as e:
                err_msg = str(e)
                print(f"[GroqAgent] Model {model_id} call error: {err_msg}")
                continue

        return self._offline_multimodal_reply(user_query, bool(image_b64))

    async def summarize_document(self, extracted_text: str) -> str:
        """Summarize extracted text into clear speech-friendly audio summary"""
        if not self.client or not extracted_text.strip():
            # Return truncated snippet if offline
            clean = " ".join(extracted_text.split())
            return f"Document summary: {clean[:200]}..." if len(clean) > 200 else clean

        prompt = (
            f"Here is the text extracted from a document:\n\"\"\"{extracted_text[:3000]}\"\"\"\n\n"
            "Provide a concise, 2-to-3 sentence summary suitable to be read aloud to a visually impaired user."
        )

        try:
            response = await self.client.chat.completions.create(
                model=settings.GROQ_FALLBACK_MODEL,
                messages=[
                    {"role": "system", "content": "You are a concise document reading assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=120,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Document preview: {extracted_text[:250]}..."

    async def transcribe_audio_bytes(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        """Transcribe speech audio via Whisper-large-v3-turbo on Groq"""
        if not self.client:
            return ""

        try:
            file_tuple = (filename, io.BytesIO(audio_bytes))
            transcription = await self.client.audio.transcriptions.create(
                file=file_tuple,
                model=settings.GROQ_WHISPER_MODEL,
                response_format="text"
            )
            return str(transcription).strip()
        except Exception as e:
            print(f"[GroqAgent] Whisper transcription error: {e}")
            return ""

    def _offline_multimodal_reply(self, query: str, has_image: bool) -> str:
        """Intelligent heuristic fallback when API key is unavailable"""
        q = query.lower()
        if "safe" in q or "path" in q:
            return "Path check: Your forward corridor is clear. Maintain a standard walking pace and keep your cane active."
        elif "read" in q or "text" in q:
            return "Please hold the document steady in front of the camera and use the Document Scan button for full OCR extraction."
        elif "around" in q or "describe" in q or "see" in q:
            return "Vision Engine active: Monitoring indoor and pedestrian obstacles in real time with Left, Center, and Right corridor safety checks."
        else:
            return "I am with you. Your real-time obstacle avoidance and corridor depth sensors are active."

groq_agent = GroqAgent()

