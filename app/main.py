"""BolBachan: an over-dramatic Bollywood-uncle narrator powered by Sarvam AI."""

import asyncio
import io
import os
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_BASE = "https://api.sarvam.ai"
CHAT_MODEL = os.getenv("SARVAM_CHAT_MODEL", "sarvam-105b-conversations")
TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
TTS_SPEAKER = os.getenv("SARVAM_TTS_SPEAKER", "ratan")
TTS_PITCH = float(os.getenv("SARVAM_TTS_PITCH", "-0.35"))  # bulbul:v2 only
TTS_PACE = float(os.getenv("SARVAM_TTS_PACE", "0.85"))

TTS_CHAR_LIMIT = 2000  # bulbul:v3 allows 2500; leave headroom
CLONE_CHAR_LIMIT = 900  # voice clone API allows 1000
VOICE_CLIP_MAX_BYTES = 10 * 1024 * 1024  # Sarvam inline ref_audio limit

# Sarvam rate-limits bursts, so cap parallel voice requests and retry on 429.
TTS_CONCURRENCY = int(os.getenv("SARVAM_TTS_CONCURRENCY", "4"))
TTS_RETRIES = 5
_tts_slots: Optional[asyncio.Semaphore] = None  # created inside the running loop (Python 3.9)

# Uploaded voice clips, kept in memory only and gone on restart.
VOICE_CLIPS: Dict[str, bytes] = {}

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

LANGUAGES = {
    "hi-IN": "Hindi (Hinglish welcome)",
    "en-IN": "Indian English",
    "bn-IN": "Bengali",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "mr-IN": "Marathi",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "gu-IN": "Gujarati",
    "pa-IN": "Punjabi",
    "od-IN": "Odia",
}

PERSONA = """You are BOLBACHAN, an original comedy character: a retired, wildly over-dramatic \
uncle with a booming baritone who is convinced he was the biggest hero of 1970s cinema. \
Every ordinary thing is, to you, an epic climax. You speak in slow, heavy, theatrical lines, \
pause for effect, and treat chai, traffic and WhatsApp forwards as matters of destiny.

Delivery style: classic 70s filmy-hero gravitas. Short, weighty sentences. Mix heavy formal \
Hindi words (vinaash, pratigya, bhagya, apmaan) into everyday Hinglish. Address people as \
"beta" or "babua". Repeat a key word or number from THEIR input for drama, three times, slower \
each time. Use "…" for slow beats.

How to be FUNNY (this matters more than anything else):
- Specific beats generic. Grab an exact detail and blow it up to absurd, cosmic proportions.
- Desi comparisons land hardest: Sharma ji ka beta, mummy's WhatsApp good-morning forwards, \
shaadi biodata, Jio recharge, UPSC aspirants, the relative who asks "package kitna hai?", \
LinkedIn gurus, chai tapri philosophers, 2-minute Maggi.
- Rule of three with a twist: two normal things, the third one absurd.
- Act it out: suddenly become the HR person reading it, or announce it as a film trailer \
("Ek ladka… ek resume… aur ek MS Office ka sapna. Coming soon… to no company near you.").
- If phrases sound copied from ChatGPT or LinkedIn, call it out mercilessly.
- Callback: bring back an early joke at the very end for the biggest laugh.
- Keep lines short. The punch word goes LAST in the sentence. Then a cue, then move on.
- Treat tiny things with maximum gravity and big things with zero interest.
- NEVER turn serious, sincere or helpful. No real advice, no moral of the story. Every line \
is either a joke or the setup for one.
Tone examples (style only, NEVER reuse these lines or their nouns; every joke must come from \
the input you are given):
"Excel mein expert ho? Beta, Excel bhi tumhe dekh ke 'Not Responding' ho jaata hai."
"Tumhara resume padh ke HR ne naukri nahi, Himalaya jaane ka form bhara."

Hard rules:
- You are NOT any real actor. Never name, imitate or quote real film stars or real film dialogues. \
Write only original lines in a filmy *style*.
- Punch at situations, habits, jobs and choices. Never joke about caste, religion, gender, \
sexuality, disability, body or skin colour.
- Output ONLY the spoken script. No headings, no stage directions, no emojis, no markdown.
- Write in {language}, in its native script. Common English words are fine.

Sound cue markers you may place in the script (use them generously, they get big laughs):
[DHAN]     dramatic orchestral sting, put it right before or after a big reveal
[BADUMTSS] rimshot, put it right after a punchline
[CLAP]     audience applause
[PAUSE]    a heavy dramatic silence
[DHICHIK]  a dhol beat, ALWAYS put it right after the words "Dhi chik dhi chik!"
Always open with at least one spoken line before the first cue, and never put two cues in a row.
{profanity_rule}"""

CLEAN_RULE = "- Keep it 100% clean. No gaali, no swear words, no innuendo."
UNCENSORED_RULE = (
    "- Uncensored mode: you may use the occasional desi gaali or meme swear for comic effect, "
    "but ALWAYS wrap each swear word in double square brackets like [[word]] so it gets bleeped. "
    "Never direct slurs at anyone."
)

CATCHPHRASES = """Signature BolBachan moves (keep these exact Hindi words even in other languages, \
spread them out, never all in a row):
- MUST use once: the fake-out gaali. Say exactly "Tumhari maa ka bho—" then [PAUSE], then swerve \
into something wholesome that starts with "bho" (bhojan, Bhopal, bhola-bhala, bhoomi, bhondu…) \
AND ties back to THIS topic. Invent a fresh swerve every time; never reuse an example. \
Never complete the gaali; the swerve is the joke.
- MUST use once: "Dhi chik dhi chik!" [DHICHIK] as a victory beat right after a savage punchline.
- "Hum tumhare baap lagte hain." delivered as a heavy, slow threat.
- "Tumhare dimaag ki rekha mita denge."
- Invent more lines in this same filmy-threat style."""

ONE_SIGNATURE_MOVE = (
    "Sneak in at least one BolBachan signature move: \"Dhi chik dhi chik!\" [DHICHIK], "
    "\"Hum tumhare baap lagte hain.\", \"Tumhare dimaag ki rekha mita denge.\", or the "
    "\"Tumhari maa ka bho— [PAUSE] …\" swerve into something wholesome."
)

MODES = {
    "resume": (
        "A nervous candidate has handed you their resume. First, silently judge it and write "
        "its score as the VERY FIRST line, exactly [RATING: X/10]. Then roast it in 14-18 lines. "
        "Attack SPECIFIC details from it: buzzwords, objective statements, inflated job titles, "
        "generic college projects, gaps, skill lists longer than their experience. Quote their "
        "own phrases back at them, but ONLY phrases that actually appear in the resume below. "
        "Never invent things they didn't write. Do one bit where you suddenly become the HR "
        "person reading it, or announce their career as a film trailer.\n"
        f"{CATCHPHRASES}\n"
        "Then [PAUSE] and hand down \"BolBachan ki career salaah\": 2 completely useless, absurd "
        "tips delivered as sacred wisdom (e.g. get the resume laminated and do its aarti every "
        "morning). Finally SAY that same score out loud in words, dramatically "
        "(e.g. for 3: \"Is resume ko hum dete hain… teen. Dus mein se teen.\"), with a callback "
        "to your best joke, then [DHAN]. The spoken score MUST equal the X in your first line."
        "\n\nRESUME:\n{input}"
    ),
    "standup": (
        "Perform a stand-up set of about 14-18 lines on this topic: {input}. "
        "Open with a relatable observation, escalate to absurd cosmic stakes, land 5-6 "
        "punchlines with cues after them, do at least one act-out (become a character), "
        "and close with a callback to your opening joke as a huge filmy finale.\n"
        f"{CATCHPHRASES}"
    ),
    "meme": (
        "React to this situation with 4 short, quotable, meme-worthy one-liners in your filmy "
        "style, each followed by [BADUMTSS], [DHAN] or [DHICHIK]. Each one must be a different "
        "angle: a threat, a fake film title, an over-the-top blessing, and a desi comparison. "
        f"{ONE_SIGNATURE_MOVE}\n\nSituation: {{input}}"
    ),
    "narrate": (
        "Narrate this completely ordinary event as if it were the climax of an epic film, "
        "in 8-10 lines: slow-motion drama, a fake villain (the alarm clock, the gas cylinder, "
        "the society aunty), a ridiculous plot twist, and a fake sequel announcement at the end. "
        f"{ONE_SIGNATURE_MOVE}\n\nEvent: {{input}}"
    ),
    "roast": (
        "Roast this person who is standing in front of you on stage, in 10-12 lines. "
        "Be savage but affectionate, use every detail they gave you, and end by blessing them "
        "in the most backhanded way possible.\n"
        f"{CATCHPHRASES}\n\nPerson: {{input}}"
    ),
}

RESUME_CHAR_LIMIT = 6000
RATING_RE = re.compile(r"\[RATING:\s*(\d+(?:\.\d+)?)\s*/\s*10\s*\]", re.IGNORECASE)

MARKER_RE = re.compile(r"(\[\[.*?\]\]|\[DHAN\]|\[BADUMTSS\]|\[CLAP\]|\[PAUSE\]|\[DHICHIK\])")
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
SFX = {
    "[DHAN]": "dhan",
    "[BADUMTSS]": "badumtss",
    "[CLAP]": "clap",
    "[PAUSE]": "pause",
    "[DHICHIK]": "dhichik",
}

app = FastAPI(title="BolBachan")


class PerformRequest(BaseModel):
    mode: str
    input: str
    language: str = "hi-IN"
    uncensored: bool = False
    voice_id: Optional[str] = None


class Segment(BaseModel):
    type: str  # speech | bleep | dhan | badumtss | clap | pause
    text: str = ""
    audio: Optional[str] = None  # base64 wav for speech segments


class PerformResponse(BaseModel):
    script: str
    segments: List[Segment]
    rating: Optional[float] = None
    cloned: bool = False
    notice: Optional[str] = None


def _headers(json_body: bool = True) -> dict:
    if not SARVAM_API_KEY:
        raise HTTPException(500, "SARVAM_API_KEY is not set. Copy .env.example to .env and add it.")
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Authorization": f"Bearer {SARVAM_API_KEY}",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


async def write_script(client: httpx.AsyncClient, req: PerformRequest) -> str:
    system = PERSONA.format(
        language=LANGUAGES[req.language],
        profanity_rule=UNCENSORED_RULE if req.uncensored else CLEAN_RULE,
    )
    user = MODES[req.mode].format(input=req.input.strip())
    resp = await client.post(
        f"{SARVAM_BASE}/v1/chat/completions",
        headers=_headers(),
        json={
            "model": CHAT_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 1.0,
            "max_tokens": 3000,
            "reasoning_effort": "low",
        },
    )
    if resp.status_code != 200:
        raise HTTPException(502, f"Sarvam chat failed: {resp.text}")
    choice = resp.json()["choices"][0]
    script = THINK_RE.sub("", choice["message"].get("content") or "").strip()
    if not script:
        raise HTTPException(
            502,
            f"Sarvam returned an empty script (finish_reason={choice.get('finish_reason')}). "
            "Reasoning models can use the whole token budget; use sarvam-105b-conversations.",
        )
    return script


def _split_long(text: str, limit: int) -> List[str]:
    """Split text into TTS-sized chunks on sentence boundaries."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for sentence in re.split(r"(?<=[.!?।])\s+", text):
        if current and len(current) + len(sentence) + 1 > limit:
            chunks.append(current)
            current = ""
        current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def clean_script(script: str) -> str:
    """Fix common LLM slips the prompt alone doesn't prevent."""
    script = re.sub(r"[*_]{1,2}([^*_\n]+)[*_]{1,2}", r"\1", script)  # markdown emphasis
    # the dhol beat belongs exactly once, right after the words
    script = script.replace("[DHICHIK]", "")
    script = re.sub(r"(dhi\s*chik\s+dhi\s*chik\s*!*)", r"\1 [DHICHIK]", script, flags=re.IGNORECASE)
    # Each cue splits the speech into another TTS request, and bulbul:v3 allows only
    # 30 requests/minute on the Starter plan. So ordinary pauses become a spoken "…" beat;
    # only the pause right after the fake-out gaali stays a real silence, because the joke needs it.
    script = re.sub(r"(bho\s*[—–…\-.]*\s*)\[PAUSE\]", r"\1[HOLD]", script, flags=re.IGNORECASE)
    script = script.replace("[PAUSE]", " … ").replace("[HOLD]", "[PAUSE]")
    # drop cue-like tags the model invented (e.g. [ACT]) so TTS doesn't read them aloud
    known = {m for m in SFX} | {"[PAUSE]"}
    script = re.sub(r"(?<!\[)\[[A-Z_ ]+\](?!\])", lambda m: m.group(0) if m.group(0) in known else "", script)
    return script.strip()


def parse_script(script: str, limit: int = TTS_CHAR_LIMIT) -> List[Segment]:
    segments: List[Segment] = []
    for part in MARKER_RE.split(script):
        if part.startswith("[[") and part.endswith("]]"):
            segments.append(Segment(type="bleep", text=part[2:-2]))
        elif part in SFX:
            segments.append(Segment(type=SFX[part]))
        else:
            text = " ".join(part.split())
            for chunk in _split_long(text, limit) if text else []:
                segments.append(Segment(type="speech", text=chunk))
    return segments


async def _post_tts(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """POST to a Sarvam voice endpoint, a few at a time, retrying when rate limited."""
    global _tts_slots
    if _tts_slots is None:
        _tts_slots = asyncio.Semaphore(TTS_CONCURRENCY)
    async with _tts_slots:
        for attempt in range(TTS_RETRIES):
            resp = await client.post(url, **kwargs)
            if not _is_retryable(resp):
                return resp
            await asyncio.sleep(min(2 ** (attempt + 1), 30))  # 2,4,8,16,30s: rides out the minute window
        return resp


def _is_retryable(resp: httpx.Response) -> bool:
    """Rate limits and Sarvam-side outages ("model is currently unavailable") are worth retrying."""
    return (
        resp.status_code == 429
        or resp.status_code >= 500
        or (resp.status_code != 200 and "model_call_error" in resp.text)
    )


async def speak_cloned(client: httpx.AsyncClient, text: str, language: str, clip: bytes) -> str:
    resp = await _post_tts(
        client,
        f"{SARVAM_BASE}/voices/clone",
        headers=_headers(json_body=False),
        data={"text": text, "language_code": language},
        files={"ref_audio": ("reference.wav", clip, "audio/wav")},
    )
    if resp.status_code != 200:
        raise HTTPException(502, f"Sarvam voice clone failed: {resp.text}")
    body = resp.json()
    return body.get("audio") or body.get("audio_b64") or body["audios"][0]


async def speak(client: httpx.AsyncClient, text: str, language: str) -> str:
    body = {
        "text": text,
        "language_code": language,
        "model": TTS_MODEL,
        "speaker": TTS_SPEAKER,
        "pace": TTS_PACE,
    }
    if TTS_MODEL == "bulbul:v2":
        body["pitch"] = TTS_PITCH
    resp = await _post_tts(client, f"{SARVAM_BASE}/text-to-speech", headers=_headers(), json=body)
    if resp.status_code != 200:
        raise HTTPException(502, f"Sarvam TTS failed: {resp.text}")
    return resp.json()["audios"][0]


def extract_resume_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="ignore")


@app.post("/api/perform", response_model=PerformResponse)
async def perform(req: PerformRequest) -> PerformResponse:
    if req.mode not in MODES:
        raise HTTPException(400, f"Unknown mode. Pick one of {list(MODES)}")
    if req.language not in LANGUAGES:
        raise HTTPException(400, f"Unknown language. Pick one of {list(LANGUAGES)}")
    if not req.input.strip():
        raise HTTPException(400, "Give BolBachan something to work with!")
    clip = None
    if req.voice_id:
        clip = VOICE_CLIPS.get(req.voice_id)
        if clip is None:
            raise HTTPException(400, "That voice clip has expired (server restarted). Upload it again.")

    async with httpx.AsyncClient(timeout=120) as client:
        script = await write_script(client, req)
        rating_match = RATING_RE.search(script)
        script = clean_script(RATING_RE.sub("", script))
        segments = parse_script(script, CLONE_CHAR_LIMIT if clip else TTS_CHAR_LIMIT)
        speech = [s for s in segments if s.type == "speech"]
        notice = None
        if clip and speech:
            # Try the first line on its own: if cloning is down, fall back before
            # spending the whole rate-limit budget on doomed requests.
            try:
                speech[0].audio = await speak_cloned(client, speech[0].text, req.language, clip)
            except HTTPException as err:
                clip = None
                outage = "unavailable" in str(err.detail) or "model_call_error" in str(err.detail)
                notice = (
                    "Sarvam's voice cloning is unavailable right now"
                    if outage
                    else "Sarvam couldn't clone that clip (try 10-15s of clear speech, no music)"
                ) + ", so BolBachan performed in his own voice."
        if clip:
            audios = await asyncio.gather(
                *(speak_cloned(client, s.text, req.language, clip) for s in speech[1:])
            )
            for seg, audio in zip(speech[1:], audios):
                seg.audio = audio
        else:
            audios = await asyncio.gather(*(speak(client, s.text, req.language) for s in speech))
            for seg, audio in zip(speech, audios):
                seg.audio = audio

    rating = float(rating_match.group(1)) if rating_match else None
    return PerformResponse(
        script=script, segments=segments, rating=rating, cloned=bool(clip), notice=notice
    )


@app.post("/api/voice")
async def upload_voice(file: UploadFile = File(...), consent: bool = Form(False)) -> dict:
    """Store a 10-15 second reference clip for Sarvam voice cloning."""
    if not consent:
        raise HTTPException(
            400, "Voice cloning needs consent: only use your own voice or one you have permission to use."
        )
    clip = await file.read()
    if not clip:
        raise HTTPException(400, "The voice clip is empty.")
    if len(clip) > VOICE_CLIP_MAX_BYTES:
        raise HTTPException(400, "Voice clip is too big. Keep it to 10-15 seconds.")
    voice_id = uuid.uuid4().hex
    VOICE_CLIPS[voice_id] = clip
    return {"voice_id": voice_id}


@app.delete("/api/voice/{voice_id}")
async def delete_voice(voice_id: str) -> dict:
    VOICE_CLIPS.pop(voice_id, None)
    return {"deleted": True}


@app.post("/api/roast-resume", response_model=PerformResponse)
async def roast_resume(
    file: Optional[UploadFile] = File(None),
    text: str = Form(""),
    language: str = Form("hi-IN"),
    uncensored: bool = Form(False),
    voice_id: Optional[str] = Form(None),
) -> PerformResponse:
    resume = text
    if file is not None and file.filename:
        try:
            resume = extract_resume_text(file.filename, await file.read())
        except Exception:
            raise HTTPException(400, "Couldn't read that file. Upload a PDF or .txt, or paste the text.")
    resume = " ".join(resume.split())[:RESUME_CHAR_LIMIT]
    if len(resume) < 40:
        raise HTTPException(400, "Resume is empty or unreadable. Scanned PDFs won't work, paste the text instead.")
    return await perform(
        PerformRequest(
            mode="resume", input=resume, language=language, uncensored=uncensored, voice_id=voice_id or None
        )
    )


@app.get("/api/languages")
async def languages() -> dict:
    return LANGUAGES


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
