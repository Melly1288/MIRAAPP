"""
Missions endpoints. Import and include this router from main.py:

    from missions_router import router as missions_router
    app.include_router(missions_router)

No changes to your existing /feedback or /review-batch logic are required
beyond adding the "mission_tags" field to their response models (see
INTEGRATION.md for the exact diff).
"""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

import mission_engine

router = APIRouter(prefix="/missions", tags=["missions"])


@router.get("/library")
async def missions_library():
    """Mobile app calls this once at launch (and caches it) to render the
    mission board - hidden names, hints, difficulty, XP. Updating mission
    content later (new missions, activating rare/legendary tiers) only
    requires editing missions_data.json + redeploying, never an app update."""
    return mission_engine.get_missions_library()


class SubmissionPayload(BaseModel):
    rating: int
    verdict: str
    next_action_type: str
    category_tag: str
    mission_tags: List[str] = []


class EvaluateRequest(BaseModel):
    mission_state: Optional[dict] = None
    submission: SubmissionPayload


@router.post("/evaluate")
async def evaluate(request: EvaluateRequest):
    """Stateless: the client sends its current mission_state (from
    AsyncStorage) plus the latest submission's result. Returns the updated
    state to overwrite in AsyncStorage, plus what's new to show the user
    (completed missions, XP, unlocked achievements)."""
    result = mission_engine.evaluate_submission(
        request.mission_state, request.submission.model_dump()
    )
    return result
