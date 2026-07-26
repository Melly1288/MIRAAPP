"""
Mira Mission Engine — stateless evaluator.

Design: the backend holds no per-user database. The mobile app stores the
user's mission_state locally (AsyncStorage) and sends its CURRENT state up
with each request; this module computes what changed and returns the
updated state. This avoids Render's ephemeral-disk problem entirely and
costs nothing extra to run during single-user testing.

When multi-user/auth lands later, the exact same functions here keep
working unchanged — only the storage location moves from AsyncStorage to
a real per-user row in a database, keyed by user_id instead of implicit
single-user. No mission-logic changes needed at that point.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_DATA_PATH = os.path.join(os.path.dirname(__file__), "missions_data.json")

with open(_DATA_PATH) as _f:
    MISSIONS_DATA = json.load(_f)

MISSIONS_BY_ID = {m["mission_id"]: m for m in MISSIONS_DATA["missions"]}
ACHIEVEMENTS_BY_ID = {a["achievement_id"]: a for a in MISSIONS_DATA["achievements"]}


def get_active_missions() -> List[dict]:
    """Missions currently enabled for detection (Phase 1: common+uncommon)."""
    return [m for m in MISSIONS_DATA["missions"] if m["active"]]


def default_mission_state() -> dict:
    """Shape of a brand-new user's mission_state, before anything is
    stored client-side. The mobile app should use this as its starting
    AsyncStorage value."""
    return {
        "completed_mission_ids": [],
        "unlocked_achievement_ids": [],
        "skill_path_xp": {path: 0 for path in MISSIONS_DATA["skill_paths"]},
        "session_ratings": [],  # ratings seen in the current session, for achievements like Straight Flush
        "category_tags_seen": [],  # for Jack of All Trades
        "last_verdict_by_subject": None,  # simplistic placeholder for Comeback Kid-style tracking (future)
    }


def _mission_criteria_met(mission: dict, submission: dict) -> bool:
    criteria = mission["criteria"]
    if criteria["type"] != "tag_match":
        return False  # only tag_match is implemented in Phase 1

    tags_present = set(submission.get("mission_tags") or [])
    required = set(criteria["required_tags"])
    match_mode = criteria.get("match_mode", "any")

    if match_mode == "all":
        tag_ok = required.issubset(tags_present)
    else:  # "any"
        tag_ok = bool(required & tags_present)

    if not tag_ok:
        return False

    min_rating = criteria.get("min_rating")
    if min_rating is not None and submission.get("rating", 0) < min_rating:
        return False

    return True


def evaluate_submission(mission_state: Optional[dict], submission: dict) -> Dict[str, Any]:
    """
    submission: {
        "rating": int,
        "verdict": str,
        "next_action_type": str,
        "category_tag": str,
        "mission_tags": [str, ...],
    }

    Returns: {
        "mission_state": <updated state to persist client-side>,
        "newly_completed": [mission summary, ...],
        "xp_awarded": int,
        "newly_unlocked_achievements": [achievement summary, ...],
    }
    """
    state = mission_state or default_mission_state()
    # defensive defaults in case an older/partial state blob comes in
    state.setdefault("completed_mission_ids", [])
    state.setdefault("unlocked_achievement_ids", [])
    state.setdefault("skill_path_xp", {p: 0 for p in MISSIONS_DATA["skill_paths"]})
    state.setdefault("session_ratings", [])
    state.setdefault("category_tags_seen", [])

    newly_completed = []
    xp_awarded = 0

    for mission in get_active_missions():
        if mission["mission_id"] in state["completed_mission_ids"]:
            continue  # each mission completes once (v1 — repeatable missions can be a later addition)
        if _mission_criteria_met(mission, submission):
            state["completed_mission_ids"].append(mission["mission_id"])
            state["skill_path_xp"][mission["skill_path"]] = (
                state["skill_path_xp"].get(mission["skill_path"], 0) + mission["xp"]
            )
            xp_awarded += mission["xp"]
            newly_completed.append({
                "mission_id": mission["mission_id"],
                "hidden_name": mission["hidden_name"],
                "difficulty": mission["difficulty"],
                "xp": mission["xp"],
                "skill_path": mission["skill_path"],
            })

    # lightweight bookkeeping for achievement checks
    state["session_ratings"].append(submission.get("rating"))
    if submission.get("category_tag") and submission["category_tag"] not in state["category_tags_seen"]:
        state["category_tags_seen"].append(submission["category_tag"])

    newly_unlocked = _check_achievements(state, submission)

    return {
        "mission_state": state,
        "newly_completed": newly_completed,
        "xp_awarded": xp_awarded,
        "newly_unlocked_achievements": newly_unlocked,
    }


def _check_achievements(state: dict, submission: dict) -> List[dict]:
    """Only the achievements checkable from state kept in this module are
    implemented here (straight_flush, jack_of_all_trades, no_filter_needed).
    The rest (batch-based, time-window-based, tier-completion-based) need
    slightly more context than a single submission carries and are flagged
    as TODO — see README for what each needs."""
    unlocked = []

    def unlock(achievement_id: str):
        if achievement_id not in state["unlocked_achievement_ids"]:
            state["unlocked_achievement_ids"].append(achievement_id)
            unlocked.append(ACHIEVEMENTS_BY_ID[achievement_id])

    # Straight Flush: ratings 1-5 all seen in this session
    if set(state["session_ratings"]) >= {1, 2, 3, 4, 5}:
        unlock("straight_flush")

    # Jack of All Trades: relies on the existing category_tag values your
    # tuned prompt already produces (lighting, composition, framing,
    # subject, focus, timing) - update this set if you add/rename any.
    known_category_tags = {"lighting", "composition", "framing", "subject", "focus", "timing"}
    if known_category_tags.issubset(set(state["category_tags_seen"])):
        unlock("jack_of_all_trades")

    # No Filter Needed: single-submission check, no state needed beyond this call
    if submission.get("next_action_type") == "keep" and submission.get("rating") == 5:
        unlock("no_filter_needed")

    return unlocked


def get_missions_library() -> dict:
    """What GET /missions/library returns - only active missions, so the
    app never has to know which difficulty tiers are live server-side."""
    return {
        "version": MISSIONS_DATA["version"],
        "difficulty_xp": MISSIONS_DATA["difficulty_xp"],
        "skill_paths": MISSIONS_DATA["skill_paths"],
        "missions": [
            {k: v for k, v in m.items() if k != "criteria"}
            for m in get_active_missions()
        ],
        "achievements": MISSIONS_DATA["achievements"],
    }
