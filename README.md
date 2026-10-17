# 🎙️ BolBachan

> *"Tumhara resume padh ke HR ne naukri nahi, Himalaya jaane ka form bhara."*
> *(Reading your resume, HR didn't fill a job form, they filled one to go to the Himalayas.)*
> **BolBachan**

Meet **BolBachan**: a retired, wildly over-dramatic uncle with a booming baritone who is *fully
convinced* he was the biggest hero of 1970s cinema. Nobody remembers his films. He remembers all of them.

Give him your resume and he will read it slowly, out loud, like a villain reading a confession.
He'll quote your "results-driven go-getter" back at you, turn your 6-week internship into an epic
tragedy, nearly say something terrible about your mother, swerve at the last second, play a
dhol beat for himself, and finally slam down a score out of 10.

It's free. It hurts. You'll share it anyway.

## ✨ What he does

| Mode | What happens |
|---|---|
| 📄 **Rate My Resume** | Upload a PDF or paste text. He roasts it line by line, hands out completely useless "career salaah", and gives a score out of 10 |
| 🎤 **Standup** | Give him any topic (Bangalore traffic, PG life, layoffs) and get a full dramatic standup set |
| 😂 **Meme Reactor** | Describe a situation and get four quotable one-liners |
| 🎬 **Dramatic Narrator** | Your boring life, narrated as an epic film climax, with a sequel announcement |
| 🔥 **Roast Me** | Tell him your name and job. Regret it. |

**His signature moves:**
- 🤐 *"Tumhari maa ka bho—"* … dramatic pause … *"…bhojan bahut swadisht hota hoga, beta."* He never finishes the gaali. The swerve is the joke.
- 🥁 *"Dhi chik dhi chik!"* followed by a dhol beat he plays for himself
- 👑 *"Hum tumhare baap lagte hain."*
- 🧠 *"Tumhare dimaag ki rekha mita denge."*

**Plus:**
- 🌏 **11 Indian languages**: Hindi/Hinglish, Tamil, Bengali, Telugu, Marathi, Kannada, Malayalam, Gujarati, Punjabi, Odia and Indian English
- 🔊 **Live sound effects** made in the browser: DHAN orchestral stings, ba-dum-tss, applause and dhol beats
- 🤬 **Uncensored mode**: real gaalis are allowed, but every one gets bleeped. The bleep is funnier anyway.
- 🎭 **Voice cloning**: record 12 seconds of a friend (with their permission) and BolBachan roasts them *in their own voice*

## 🛠️ Built with

- [Sarvam AI](https://www.sarvam.ai/) chat LLM (`sarvam-105b-conversations`) writes the script in character
- [Sarvam Bulbul v3](https://www.sarvam.ai/) text-to-speech gives him a voice, and Sarvam voice cloning handles the "your own voice" trick
- FastAPI backend, plain HTML/JS frontend
- Web Audio API for the deep-voice effect (bass boost and hall reverb) and every sound effect, with no audio files shipped

## 🚀 Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your SARVAM_API_KEY
uvicorn app.main:app --port 8010
```

Open http://localhost:8010, drop in a resume, turn the volume up, and click **Perform!**

## ⚙️ How it works

1. The Sarvam LLM writes a script in the BolBachan persona and marks sound cues in it:
   `[DHAN]`, `[BADUMTSS]`, `[CLAP]`, `[DHICHIK]`, `[PAUSE]` and `[[swear]]`. Anything in `[[ ]]` is bleeped and never spoken.
2. The backend splits the script at those cues and sends the speech chunks to Bulbul TTS,
   a few at a time, retrying when Sarvam's rate limit kicks in.
3. The browser plays everything in order with live captions, then slams the score onto the screen.

### Tuning

| `.env` variable | What it does |
|---|---|
| `SARVAM_TTS_SPEAKER` | Which Bulbul v3 voice he uses (default `ratan`) |
| `SARVAM_TTS_PACE` | Speaking speed. Slower sounds more dramatic (default `0.8`) |
| `SARVAM_TTS_CONCURRENCY` | Voice requests sent at once (default `4`). The Starter plan allows 30 per minute |

## 🙏 Ground rules

- BolBachan is an **original character**. He doesn't imitate any real actor, and his lines are written fresh every time.
- Roasts go after resumes, habits and choices. They never target caste, religion, gender, body or anything else a person can't change.
- **Voice cloning needs consent.** Only clone your own voice or a voice whose owner has said yes. The app asks every time.
- Resumes are sent to Sarvam to generate the roast. Clips are kept in server memory only and disappear on restart.
