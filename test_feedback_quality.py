"""
Quality-test script for Mira's feedback prompt.

Point this at a folder of 15-20 real amateur photos (yours, friends',
whatever) and it will print Mira's feedback for each one, plus a rough
token-cost estimate. This is the single most important test before
building any UI: does the feedback feel specific and useful, or generic
and fortune-cookie-ish?

Usage:
    export ANTHROPIC_API_KEY=your-key-here
    python test_feedback_quality.py /path/to/photos/folder
"""

import base64
import json
import os
import sys
from pathlib import Path

import anthropic

# Reuse the same prompt and model as main.py so this test reflects
# exactly what the real endpoint will do.
from main import MODEL, SYSTEM_PROMPT, build_media_type, parse_feedback_json

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def run_test(folder_path: str):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    photos = [
        p for p in Path(folder_path).iterdir()
        if p.suffix.lower() in IMAGE_EXTENSIONS
    ]

    if not photos:
        print(f"No image files found in {folder_path}")
        return

    print(f"Testing feedback quality on {len(photos)} photos...\n")
    print("=" * 70)

    total_input_tokens = 0
    total_output_tokens = 0
    parse_failures = 0

    for photo_path in sorted(photos):
        with open(photo_path, "rb") as f:
            image_bytes = f.read()

        media_type = build_media_type(photo_path.name, None)
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

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
                        {"type": "text", "text": "Review this photo."},
                    ],
                }
            ],
        )

        raw_text = "".join(b.text for b in response.content if b.type == "text")

        print(f"\nPhoto: {photo_path.name}")
        try:
            feedback = parse_feedback_json(raw_text)
            stars = "★" * feedback["rating"] + "☆" * (5 - feedback["rating"])
            next_action = feedback["next_action"]
            print(f"  Rating:       {stars} ({feedback['rating']}/5)")
            print(f"  Verdict:      {feedback['verdict']}")
            print(f"  Next action:  [{next_action['type']}] {next_action['label']}")
            print(f"  Category:     {feedback['category_tag']}")
        except ValueError as exc:
            parse_failures += 1
            print(f"  [PARSE FAILED] {exc}")

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        print("-" * 70)

    # Rough cost estimate at published Haiku 4.5 rates ($1/$5 per MTok)
    input_cost = (total_input_tokens / 1_000_000) * 1.00
    output_cost = (total_output_tokens / 1_000_000) * 5.00
    total_cost = input_cost + output_cost

    print(f"\nTotal photos tested: {len(photos)}")
    print(f"Parse failures:      {parse_failures}")
    print(f"Total input tokens:  {total_input_tokens:,}")
    print(f"Total output tokens: {total_output_tokens:,}")
    print(f"Estimated cost:      ${total_cost:.4f}")
    print(f"Avg cost per photo:  ${total_cost / len(photos):.4f}")
    print("\nRead through the feedback above and ask three things:")
    print("1. Does each verdict reference something SPECIFIC and real in")
    print("   that photo, or could it apply to almost any photo?")
    print("2. Does every response actually end with ONE clear next_action")
    print("   you could imagine tapping as a button?")
    print("3. Does the next_action.type feel right for that photo (would")
    print("   YOU have called it keep/enhance/retake/archive)?")
    print("That's the quality bar to hit before building any UI around this.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_feedback_quality.py /path/to/photos/folder")
        sys.exit(1)

    run_test(sys.argv[1])
