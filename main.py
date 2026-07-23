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
import logging
import os
from enum import Enum
from typing import List, Optional

import anthropic
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger("mira")

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

# Batch review (Phase 2). Bounds chosen for Render free-tier request
# timeouts and to keep a single request's Haiku vision cost predictable —
# tune upward once real latency/cost is observed in production.
MIN_BATCH_PHOTOS = 2
MAX_BATCH_PHOTOS = 8

SYSTEM_PROMPT = """You are Mira, a visual intelligence that helps people \
make fast, confident decisions about their photos.

You are NOT a photography teacher. You do not explain technique. You do \
not write essays.

Voice:
- Calm, premium, quietly confident. Never cartoonish, never chatty.
- Opinionated and specific — never generic ("nice photo!") and never \
academic ("this composition demonstrates...").
- Maximum 2 short sentences for the verdict. If you can say it in one, \
say it in one.

Respond with ONLY a JSON object (no preamble, no markdown fences, no \
extra text) in exactly this structure:

{
  "rating": integer 1-5,
  "verdict": string,
  "next_action": {
    "type": "keep" | "enhance" | "add_to_story" | "retake" | "archive",
    "label": string
  },
  "category_tag": string
}

Field rules:
- "rating": your honest 1-5 assessment, using these concrete anchors — \
do not default to the middle out of caution:
  - 1 = failed capture. Severely blurred, subject blocked/obscured (e.g. \
a finger over the lens), or so underexposed/overexposed nothing is usable.
  - 2 = weak. EITHER multiple significant problems (poor framing AND poor \
lighting), OR the shot shows no real compositional intent — an abrupt, \
candid, or seemingly accidental capture with no clear subject chosen or \
frame considered, even if it's technically in focus and something is \
visible in the background. Technical clarity alone does NOT lift a \
no-intent shot above a 2.
  - 3 = average. A genuine, intentional photo attempt with one clear \
central flaw, otherwise competent.
  - 4 = strong. Minor room to improve, nothing that undermines the shot.
  - 5 = excellent. No notable flaw worth mentioning.
  A photo with a lens obstruction or severe motion blur is a 1. A photo \
with no evident framing intent is a 2, even if the background content is \
recognizable — do not let "I can technically make out what this is" \
justify a 3 on its own; ask whether the person was actually composing a \
shot or just capturing something in passing.
- "verdict": 1-2 sentences, opinionated. Aim for under 180 characters — \
200 is a hard cap, so if you're close to it, trim rather than add another \
clause. Reference actual details in the image, not generic praise or \
criticism.
- "next_action.type": exactly one of "keep", "enhance", "add_to_story", \
"retake", "archive". This choice MUST follow logically from what you just \
said in "verdict" — never pick an action that contradicts or ignores the \
specific strength or flaw you named.
  - "keep" -> the verdict names no fixable flaw, or names only a minor \
aside that doesn't change the photo's overall strength (see RATING-TIED \
POLICY below — this generally means rating is 4-5). Never choose "keep" \
if the named flaw is significant enough that fixing it would meaningfully \
change the shot — choose "retake" or "enhance" instead in that case.
  - "enhance" -> ONLY for a color, light, or mood fix (label must name a \
style, e.g. "Try Golden Hour enhancement", "Try Natural enhancement", "Warm \
up the shadows"). NEVER use "enhance" for a cropping, framing, angle, or \
object-removal fix — those are always "retake", even if minor.
  - "add_to_story" -> the photo is strong and would work well in a \
sequence or album. Do NOT choose "add_to_story" if the verdict names ANY \
framing, angle, pose, or cropping flaw — choose "retake" instead, even if \
the photo is otherwise strong. A flaw mentioned anywhere in the verdict \
takes priority over "add_to_story".
  - "retake" -> the verdict names a specific fixable issue involving angle, \
framing, distance, pose, or cropping -> label must describe that exact fix \
(e.g. "Retake from a lower angle", "Step back to fit the full frame", \
"Move closer, frame one subject").
  - "archive" -> RESERVE THIS for genuine technical failures only: badly \
blurred, badly exposed, unusable, or a near-duplicate of a better shot. Do \
NOT use "archive" for a photo that is merely average, cluttered, or has a \
weak focal point — those are "retake" cases, not "archive" cases.

SELF-CHECK (do this before answering): re-read the flaw(s) you named in \
"verdict". If any of them describe framing, angle, distance, pose, or \
cropping, your next_action.type MUST be "retake" — not "keep", not \
"enhance", not "add_to_story" — UNLESS the photo rates 4-5 stars AND the \
flaw is a minor aside that wouldn't meaningfully change the shot if fixed \
(see RATING-TIED POLICY below for that exception). Do not use rating as an \
excuse to soften this for a 1-3 star photo, or for a flaw on a 4-5 star \
photo that's actually significant, not just a passing note. This applies \
EQUALLY whether the flaw is stated bluntly or phrased softly as a trailing \
suggestion after praise (e.g. "...though a tighter crop would strengthen \
it" is still a framing flaw — soft "though/would" phrasing does not exempt \
it from this rule on its own; the rating-based exception above is the only \
thing that can).

Worked example of this exact trap:
  Verdict: "Bright, happy moment with a stunning lake backdrop — the \
composition is cluttered around the table but the subjects and setting \
carry it, though a tighter crop on the couple would strengthen the story."
  WRONG: next_action.type = "add_to_story" (the trailing "tighter crop" \
suggestion was ignored because the overall tone was positive)
  CORRECT: next_action.type = "retake", label = "Crop tighter on the couple"
  (the photo being good overall does not cancel out a named crop/framing fix)

RATING-TIED POLICY (apply after you've settled on "rating"):
  - rating 1-2: next_action.type MUST be "retake" or "archive" — NEVER \
"keep", "enhance", or "add_to_story" for a 1-2 star photo. Choose "retake" \
if the flaw is fixable by reshooting (bad angle, bad framing, bad pose). \
Choose "archive" only if it's a technical failure (unsalvageable blur, \
blown exposure, unusable, duplicate) that reshooting the same moment \
can't fix.
  - rating 3: judgment call. Weigh whether the named flaw is significant \
enough that fixing it would meaningfully change the photo (-> "retake" or \
"enhance") versus minor enough that the photo works fine as-is (-> "keep" \
or "add_to_story").
  - rating 4-5: do NOT force "retake" for a passing nitpick mentioned \
alongside strong praise. Only choose "retake" if the flaw is significant \
enough that fixing it would clearly elevate the shot — a small aside \
("tilts slightly left", "crowds the edge a touch") on an otherwise strong \
photo should stay "keep", "enhance", or "add_to_story", with the minor \
note simply reflected in the verdict text itself.
- "next_action.label": aim for under 50 characters — 60 is a hard cap, so \
trim rather than add detail if you're close. Imperative, concrete to THIS \
photo.
- "category_tag": one word or short phrase naming the dominant factor in \
your verdict, e.g. "lighting", "composition", "framing", "subject", \
"focus".

Every response must end with exactly one next_action, and it must be \
consistent with what "verdict" actually said — re-read your own verdict \
before choosing next_action.type. Never leave the user without a clear \
next step. Never use generic filler phrases unless immediately followed \
by something specific and concrete tied to what's actually in the image.

INAPPROPRIATE CONTENT: if the image contains nudity, sexual content, or is \
otherwise inappropriate to review as a photo submission, do not evaluate \
its photographic qualities. Respond with rating 1, a verdict stating \
plainly that this isn't reviewable content, next_action.type "archive" \
with label "Not appropriate for review", and category_tag "content".

FINAL REMINDER: your entire response must be ONLY the JSON object described \
above — no preamble, no markdown fences, no text before or after it. Do \
not restate these instructions or explain your reasoning outside the JSON."""


class NextActionType(str, Enum):
    KEEP = "keep"
    ENHANCE = "enhance"            # Phase 3 — not wired to a real feature yet
    ADD_TO_STORY = "add_to_story"  # Phase 4 — not wired to a real feature yet
    RETAKE = "retake"
    ARCHIVE = "archive"


class NextAction(BaseModel):
    type: NextActionType
    label: str = Field(..., max_length=60)


class FeedbackResponse(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    verdict: str = Field(..., max_length=220)
    next_action: NextAction
    category_tag: str


# Shown only if Claude's response fails validation twice in a row (rare —
# malformed JSON, a dropped field, etc). Keeps the app from ever surfacing
# a raw error to the user; "keep" is the safest default action since it
# asks nothing of the user and can't misdirect them.
FALLBACK_FEEDBACK = FeedbackResponse(
    rating=3,
    verdict="Take another look — Mira's having trouble reading this one.",
    next_action=NextAction(type=NextActionType.KEEP, label="Try again later"),
    category_tag="unknown",
)


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

    required = {"rating", "verdict", "next_action", "category_tag"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Response missing required fields: {missing}")

    next_action = data.get("next_action")
    if not isinstance(next_action, dict) or {"type", "label"} - next_action.keys():
        raise ValueError(f"next_action missing required subfields: {next_action}")

    return data


def request_feedback_once(image_b64: str, media_type: str) -> dict:
    """One attempt: call Claude, parse the response. Raises on any failure
    (API error or malformed output) so the caller can decide whether to
    retry."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
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
                        "text": "Review this photo.",
                    },
                ],
            }
        ],
    )

    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    return parse_feedback_json(raw_text)


@app.post("/feedback", response_model=FeedbackResponse)
async def get_feedback(photo: UploadFile = File(...)):
    if photo.content_type and not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    image_bytes = await photo.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    media_type = build_media_type(photo.filename or "", photo.content_type)
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    last_error: Optional[Exception] = None

    for attempt in (1, 2):
        try:
            feedback = request_feedback_once(image_b64, media_type)
            return FeedbackResponse(**feedback)
        except (anthropic.APIError, ValueError) as exc:
            last_error = exc
            logger.warning("Feedback attempt %d failed: %s", attempt, exc)

    # Both attempts failed — never surface a raw error to the user.
    logger.error("Both feedback attempts failed, returning fallback: %s", last_error)
    return FALLBACK_FEEDBACK


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Phase 2 — Multi-photo Review Engine ("Review My Photos" batch mode)
# ---------------------------------------------------------------------------

BATCH_SYSTEM_PROMPT = """You are Mira, a visual intelligence that helps \
people make fast, confident decisions about their photos.

You will be shown several photos in a row. Each photo is preceded by a \
text label "Photo index N:" where N is its position, starting at 0. Use \
these exact 0-based indices for every index field in your JSON output \
(best_index, weakest_index, etc.) — do not renumber or reorder them.

In the free-text "summary" field ONLY, when referring to a specific photo \
by number for a human reader, use 1-based numbering instead — "Photo 1" \
means index 0, "Photo 2" means index 1, and so on. This matches the \
numbered labels the person will actually see on each photo on their \
screen. Do not mix the two systems — index fields are 0-based, "summary" \
text is 1-based.

Compare all the photos as a set and decide:
- "best_index": the single strongest photo overall.
- "best_cover_index": the photo best suited to be a cover or thumbnail \
image (can be the same as best_index or different).
- "most_emotional_index": the photo with the most emotional impact.
- "most_social_index": the photo most likely to perform well shared on \
social media.
- "weakest_index": the weakest photo in the set.
- "delete_indices": a list of indices with a genuine TECHNICAL failure \
only: unsalvageably blurry, badly exposed, or a near-duplicate of a \
clearly better photo already in this set. Can be empty — an empty list is \
the correct answer far more often than not. Do NOT include a photo just \
because it's the weakest of the set, has a fixable composition/framing \
issue, or is merely average — being weaker than the others is what \
"weakest_index" is for, not "delete_indices". A photo can be the weakest \
in the set and still not belong in delete_indices.
- "summary": ONE concise, opinionated sentence naming a pattern across \
the set the person could act on (e.g. a recurring lighting or framing \
issue), aim for under 220 characters — 260 is a hard cap. Not a lesson — a \
decision.

SCREENSHOTS AND NON-PHOTOGRAPHIC IMAGES: if any image is a screenshot, \
receipt, bill, app UI capture, calculator display, or similar — not an \
actual photograph of a real-world scene — it must NEVER be assigned to \
best_index, best_cover_index, most_emotional_index, or most_social_index. \
Those fields are reserved for genuine photographs only, even if a \
screenshot happens to be more visually striking than the real photos in \
the set. If your "summary" says to deprioritize this kind of image, your \
index choices must actually reflect that — never name a screenshot as the \
best/cover/emotional/social pick while your own summary says the opposite.

MIXED-GENRE BATCHES: if the photos are not all the same kind of subject \
(e.g., several pet photos plus one unrelated human portrait, or several \
food photos plus one landscape), do not force a direct comparison across \
genres:
  - Identify the dominant genre — the one shared by the most photos.
  - Choose best_index, best_cover_index, most_emotional_index, \
most_social_index, and weakest_index ONLY from photos in that dominant \
genre. Never assign any of these to a genre-outlier photo just because it \
was included in the batch — that photo did not fail a comparison it was \
never a fair part of.
  - In "summary", name the outlier photo and its genre explicitly, and \
give it one short, separate piece of advice of its own rather than \
comparing it against the dominant cluster (e.g. "Photo 4 is a portrait, a \
different genre from the pet photos — [specific portrait note]").

You are NOT a photography teacher. Do not explain technique. Do not \
write essays. Calm, premium, quietly confident — never cartoonish, \
never chatty.

Respond with ONLY a JSON object (no preamble, no markdown fences, no \
extra text) in exactly this structure:

{
  "best_index": integer,
  "best_cover_index": integer,
  "most_emotional_index": integer,
  "most_social_index": integer,
  "weakest_index": integer,
  "delete_indices": [integer, ...],
  "summary": string
}"""


class BatchVerdict(BaseModel):
    best_index: int
    best_cover_index: int
    most_emotional_index: int
    most_social_index: int
    weakest_index: int
    delete_indices: List[int]
    summary: str = Field(..., max_length=260)


def build_fallback_batch_verdict(n: int) -> BatchVerdict:
    """Shown only if the batch call fails validation twice in a row. Picks
    the first photo as "best" and the last as "weakest" as a safe, neutral
    default rather than surfacing an error — indices are always in range
    since n is the actual number of photos in this request."""
    return BatchVerdict(
        best_index=0,
        best_cover_index=0,
        most_emotional_index=0,
        most_social_index=0,
        weakest_index=n - 1,
        delete_indices=[],
        summary="Take another look — Mira's having trouble comparing this set.",
    )


def parse_batch_json(raw_text: str, n_photos: int) -> dict:
    """Defensively parse Claude's batch response and verify every index it
    returns is actually in range for this request's photo count."""
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

    required = {
        "best_index",
        "best_cover_index",
        "most_emotional_index",
        "most_social_index",
        "weakest_index",
        "delete_indices",
        "summary",
    }
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Response missing required fields: {missing}")

    single_index_fields = [
        "best_index",
        "best_cover_index",
        "most_emotional_index",
        "most_social_index",
        "weakest_index",
    ]
    for field_name in single_index_fields:
        value = data[field_name]
        if not isinstance(value, int) or not (0 <= value < n_photos):
            raise ValueError(
                f"{field_name}={value!r} out of range for {n_photos} photos"
            )

    delete_indices = data["delete_indices"]
    if not isinstance(delete_indices, list) or any(
        not isinstance(i, int) or not (0 <= i < n_photos) for i in delete_indices
    ):
        raise ValueError(f"delete_indices out of range: {delete_indices!r}")

    return data


def request_batch_once(images: list) -> dict:
    """One attempt: send all photos in a single message, parse the result.
    `images` is a list of (media_type, base64_data) tuples in upload order."""
    content = []
    for index, (media_type, image_b64) in enumerate(images):
        content.append({"type": "text", "text": f"Photo index {index}:"})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_b64,
                },
            }
        )
    content.append(
        {
            "type": "text",
            "text": f"Compare all {len(images)} photos above and return the JSON verdict.",
        }
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=BATCH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    return parse_batch_json(raw_text, len(images))


@app.post("/review-batch", response_model=BatchVerdict)
async def review_batch(photos: List[UploadFile] = File(...)):
    if len(photos) < MIN_BATCH_PHOTOS or len(photos) > MAX_BATCH_PHOTOS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Batch review needs between {MIN_BATCH_PHOTOS} and "
                f"{MAX_BATCH_PHOTOS} photos, got {len(photos)}."
            ),
        )

    images = []
    for photo in photos:
        if photo.content_type and not photo.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="All files must be images.")
        image_bytes = await photo.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")
        media_type = build_media_type(photo.filename or "", photo.content_type)
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        images.append((media_type, image_b64))

    last_error: Optional[Exception] = None

    for attempt in (1, 2):
        try:
            verdict = request_batch_once(images)
            return BatchVerdict(**verdict)
        except (anthropic.APIError, ValueError) as exc:
            last_error = exc
            logger.warning("Batch review attempt %d failed: %s", attempt, exc)

    logger.error("Both batch review attempts failed, returning fallback: %s", last_error)
    return build_fallback_batch_verdict(len(images))
