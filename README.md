# Mira - Phase 1 Backend

The entire Phase 1 MVP loop, backend-only: submit a photo, get structured
coaching feedback from Claude. No database, no UI yet — this is step 1,
built to be tested before you invest in anything else.

## Setup

```bash
cd mira_phase1
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key-here   # Windows: set ANTHROPIC_API_KEY=your-key-here
```

Get an API key at https://console.anthropic.com if you don't have one yet.
New accounts get some free credits, which is enough to run the quality
test below several times over.

## Step 1: Test feedback quality (do this FIRST, before running the server)

Gather 15-20 real amateur photos — yours, a friend's, whatever's on your
phone. Mixed quality is good: some decent shots, some obviously flawed
ones (bad lighting, awkward framing, blurry). Put them all in one folder.

```bash
python test_feedback_quality.py /path/to/your/photos/folder
```

This prints Mira's feedback for every photo plus the actual dollar cost,
using the exact same prompt and model the real app will use. Read through
every response and ask one question: **does each comment reference
something specific and real in that photo, or could it apply to almost
any photo?**

If the feedback feels specific and useful — proceed to building the app
around it. If it feels generic or repetitive, that's a signal to iterate
on the SYSTEM_PROMPT in `main.py` before building anything else. This is
the cheapest, fastest way to find out if the core idea works before
spending time on UI.

## Step 2: Run the actual API server

```bash
uvicorn main:app --reload --port 8000
```

Test it with a single photo:

```bash
curl -X POST http://localhost:8000/feedback \
  -F "photo=@/path/to/a/photo.jpg"
```

You should get back JSON like:

```json
{
  "strength": "...",
  "fix": "...",
  "fix_category": "composition",
  "encouragement": "..."
}
```

Check the server is alive any time with:

```bash
curl http://localhost:8000/health
```

## What's deliberately NOT here yet

- No database — nothing is saved between requests
- No user accounts
- No mobile UI
- No missions, tiers, or community features

That's intentional. This is the smallest possible version of the core
value proposition, built to prove the feedback loop is good before
anything else gets built on top of it.

## Next steps once feedback quality checks out

1. Add a Postgres database (Supabase or Railway free tier) to persist
   submissions and build the personal gallery
2. Build the React Native / Expo mobile screens around this endpoint
3. Real user test with 10-15 people using the actual app for a week
