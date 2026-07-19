"""
Mira - Phase 1 MVP Backend
Single endpoint: submit a photo, get structured coaching feedback from Claude.

Run locally:
    uvicorn main:app --reload --port 8000

Test it:
    curl -X POST http://localhost:8000/feedback \
      -F "photo=@/path/to/your/photo.jpg"
"""

import base64
import json
import os
from typing import Optional

import anthropic
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Mira Phase 1 - Photo Feedback API")

# Allow the mobile app / Expo dev client to call this during development.
# Tighten this to your actual app domain before shipping to production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are Mira, a warm, encouraging photography coach for \
amateur travelers using phones or beginner cameras. A user has submitted a \
photo. Respond with ONLY a JSON object (no preamble, no markdown fences, no \
extra text) in exactly this structure:

{
  "strength": string,
  "fix": string,
  "fix_category": string,
  "encouragement": string
}

Field rules:
- "strength": one short sentence naming something specific and genuine \
this photo does well. Reference actual details in the image, not generic \
praise.
- "fix": one specific, actionable adjustment referencing concrete elements \
visible in THIS photo (e.g. "step left so the doorway behind you isn't \
splitting the frame" — not "improve your background"). Must be achievable \
in under 30 seconds on a retake. No equipment purchases, no editing \
software.
- "fix_category": exactly one of "composition", "lighting", \
"focus_stability", "framing", "timing".
- "encouragement": one short, forward-looking sentence tied to this \
specific photo, not a generic "keep it up!".

Never use generic filler phrases ("great shot!", "nice angle!") unless \
immediately followed by a specific, concrete reason tied to what's \
actually in the image. Keep the entire JSON payload's text under 60 words \
combined. If the photo is already strong, make "fix" a refinement \
(e.g. "try this same framing at golden hour") rather than inventing a flaw."""


class FeedbackResponse(BaseModel):
    strength: str
    fix: str
    fix_category: str
    encouragement: str


def build_media_type(filename: str, content_type: Optional[str]) -> str:
    """Best-effort mime type resolution so Claude gets a valid image media_type."""
    if content_type and content_type.startswith("image/"):
        return content_type
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "heic": "image/heic",
    }.get(ext, "image/jpeg")


def parse_feedback_json(raw_text: str) -> dict:
    """Defensively parse Claude's response in case of stray whitespace/fences."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON: {exc}\nRaw: {raw_text}")

    required = {"strength", "fix", "fix_category", "encouragement"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Response missing required fields: {missing}")

    return data


@app.post("/feedback", response_model=FeedbackResponse)
async def get_feedback(photo: UploadFile = File(...)):
    if photo.content_type and not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    image_bytes = await photo.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    media_type = build_media_type(photo.filename or "", photo.content_type)
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Give me feedback on this photo.",
                        },
                    ],
                }
            ],
        )
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}")

    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    )

    try:
        feedback = parse_feedback_json(raw_text)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return FeedbackResponse(**feedback)


@app.get("/health")
async def health():
    return {"status": "ok"}
