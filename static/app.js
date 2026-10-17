// BolBachan front end: fetches a performance and plays it with filmy audio effects.

const PLACEHOLDERS = {
  resume: "…or paste your resume text here",
  standup: "Topic: Bangalore traffic, PG life, startup layoffs…",
  meme: "Situation: my code worked on the first try",
  narrate: "Ordinary event: I am going to make chai",
  roast: "Name + what they do: Rohan, frontend dev who centers divs for a living",
};

let mode = "resume";
let lastSegments = null;
let lastRating = null;
let lastCloned = false;
let resumeFile = null;
let voiceId = null;
let ctx = null;
let voiceChain = null;

const $ = (id) => document.getElementById(id);
const input = $("input");
const captions = $("captions");
const performBtn = $("perform");
const replayBtn = $("replay");
const mic = $("mic");
const dropzone = $("dropzone");
const ratingBox = $("rating");

// ---------- audio graph ----------

function audio() {
  if (!ctx) {
    ctx = new AudioContext();
    voiceChain = buildVoiceChain();
  }
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
}

// Deep "baritone legend" sound: bass boost + hall reverb.
function buildVoiceChain() {
  const bass = ctx.createBiquadFilter();
  bass.type = "lowshelf";
  bass.frequency.value = 200;
  bass.gain.value = 9;

  // soften the top end so the voice sounds older and heavier
  const warm = ctx.createBiquadFilter();
  warm.type = "highshelf";
  warm.frequency.value = 4500;
  warm.gain.value = -5;

  const reverb = ctx.createConvolver();
  reverb.buffer = impulse(2.8, 2.2);
  const wet = ctx.createGain();
  wet.gain.value = 0.35;

  bass.connect(warm);
  warm.connect(ctx.destination);
  warm.connect(reverb).connect(wet).connect(ctx.destination);
  return bass;
}

function impulse(seconds, decay) {
  const len = ctx.sampleRate * seconds;
  const buf = ctx.createBuffer(2, len, ctx.sampleRate);
  for (let c = 0; c < 2; c++) {
    const data = buf.getChannelData(c);
    for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, decay);
  }
  return buf;
}

function noiseBuffer(seconds) {
  const buf = ctx.createBuffer(1, ctx.sampleRate * seconds, ctx.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  return buf;
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function playSpeech(b64, cloned) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const buf = await ctx.decodeAudioData(bytes.buffer);
  const src = ctx.createBufferSource();
  src.buffer = buf;
  // slower and deeper for BolBachan; a cloned voice stays recognisable
  src.playbackRate.value = cloned ? 1 : 0.9;
  src.connect(voiceChain);
  mic.classList.add("talking");
  await new Promise((r) => { src.onended = r; src.start(); });
  mic.classList.remove("talking");
}

function bleep() {
  const t = ctx.currentTime;
  const osc = ctx.createOscillator();
  const g = ctx.createGain();
  osc.frequency.value = 1000;
  g.gain.setValueAtTime(0.25, t);
  g.gain.setValueAtTime(0, t + 0.45);
  osc.connect(g).connect(ctx.destination);
  osc.start(t);
  osc.stop(t + 0.5);
  return wait(550);
}

// Three descending orchestral stabs + a cymbal swell.
function dhan() {
  const t0 = ctx.currentTime;
  [0, 0.45, 0.9].forEach((offset, i) => {
    const t = t0 + offset;
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 900;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.35, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + (i === 2 ? 1.6 : 0.4));
    lp.connect(g).connect(ctx.destination);
    [1, 1.5, 2].forEach((mult) => {
      const osc = ctx.createOscillator();
      osc.type = "sawtooth";
      osc.frequency.value = [110, 104, 92.5][i] * mult;
      osc.connect(lp);
      osc.start(t);
      osc.stop(t + 1.7);
    });
  });
  const crash = ctx.createBufferSource();
  crash.buffer = noiseBuffer(2);
  const hp = ctx.createBiquadFilter();
  hp.type = "highpass";
  hp.frequency.value = 5000;
  const cg = ctx.createGain();
  cg.gain.setValueAtTime(0.0001, t0 + 0.9);
  cg.gain.exponentialRampToValueAtTime(0.2, t0 + 0.95);
  cg.gain.exponentialRampToValueAtTime(0.0001, t0 + 2.5);
  crash.connect(hp).connect(cg).connect(ctx.destination);
  crash.start(t0 + 0.9);
  return wait(2300);
}

function drum(t, freq, dur) {
  const osc = ctx.createOscillator();
  const g = ctx.createGain();
  osc.frequency.setValueAtTime(freq, t);
  osc.frequency.exponentialRampToValueAtTime(freq / 2, t + dur);
  g.gain.setValueAtTime(0.5, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  osc.connect(g).connect(ctx.destination);
  osc.start(t);
  osc.stop(t + dur);
}

function badumtss() {
  const t = ctx.currentTime;
  drum(t, 220, 0.15);
  drum(t + 0.18, 160, 0.2);
  const hat = ctx.createBufferSource();
  hat.buffer = noiseBuffer(1);
  const hp = ctx.createBiquadFilter();
  hp.type = "highpass";
  hp.frequency.value = 7000;
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.3, t + 0.4);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 1.2);
  hat.connect(hp).connect(g).connect(ctx.destination);
  hat.start(t + 0.4);
  return wait(1200);
}

// Dhol beat: "dhi" = deep bass thump, "chik" = sharp high slap. Played twice: dhi chik dhi chik.
function dhichik() {
  const t0 = ctx.currentTime;
  const hit = (t, freq, dur, vol) => {
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.frequency.setValueAtTime(freq, t);
    osc.frequency.exponentialRampToValueAtTime(freq * 0.5, t + dur);
    g.gain.setValueAtTime(vol, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    osc.connect(g).connect(ctx.destination);
    osc.start(t);
    osc.stop(t + dur);
  };
  const slap = (t) => {
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer(0.12);
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 3200;
    bp.Q.value = 1.2;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.5, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.1);
    src.connect(bp).connect(g).connect(ctx.destination);
    src.start(t);
    hit(t, 520, 0.08, 0.25); // wooden "tak" body
  };
  const step = 0.24;
  for (let i = 0; i < 2; i++) {
    const t = t0 + i * step * 2;
    hit(t, 95, 0.35, 0.8); // dhi
    slap(t + step); // chik
  }
  hit(t0 + step * 4, 80, 0.6, 0.9); // final boom
  return wait(step * 4 * 1000 + 600);
}

// Applause: lots of tiny random noise claps.
function clap() {
  const t0 = ctx.currentTime;
  const bp = ctx.createBiquadFilter();
  bp.type = "bandpass";
  bp.frequency.value = 1500;
  bp.Q.value = 0.8;
  bp.connect(ctx.destination);
  for (let i = 0; i < 140; i++) {
    const t = t0 + Math.random() * 2.2;
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer(0.05);
    const g = ctx.createGain();
    const peak = 0.15 * (1 - (t - t0) / 2.6);
    g.gain.setValueAtTime(peak, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.04);
    src.connect(g).connect(bp);
    src.start(t);
  }
  return wait(2400);
}

const SFX = { dhan, badumtss, clap, dhichik, bleep, pause: () => wait(1200) };

// ---------- UI ----------

function renderCaptions(segments) {
  captions.innerHTML = "";
  return segments.map((seg) => {
    const el = document.createElement("span");
    if (seg.type === "speech") el.textContent = seg.text + " ";
    else if (seg.type === "bleep") { el.textContent = "#@$%!"; el.className = "bleep"; }
    else if (seg.type === "pause") el.textContent = "… ";
    else { el.textContent = `[${seg.type.toUpperCase()}]`; el.classList.add("cue"); }
    captions.appendChild(el);
    return el;
  });
}

function showRating(rating) {
  $("ratingValue").textContent = Number.isInteger(rating) ? rating : rating.toFixed(1);
  document.querySelector(".rating-score").classList.toggle("low", rating < 5);
  ratingBox.hidden = false;
  // restart the slam animation
  ratingBox.style.animation = "none";
  void ratingBox.offsetWidth;
  ratingBox.style.animation = "";
}

async function play(segments, rating, cloned) {
  audio();
  ratingBox.hidden = true;
  const els = renderCaptions(segments);
  replayBtn.disabled = true;
  for (let i = 0; i < segments.length; i++) {
    els[i].classList.add("now");
    const seg = segments[i];
    if (seg.type === "speech" && seg.audio) await playSpeech(seg.audio, cloned);
    else if (SFX[seg.type]) await SFX[seg.type]();
    els[i].classList.replace("now", "done");
  }
  if (rating != null) {
    showRating(rating);
    clap();
  }
  replayBtn.disabled = false;
}

function buildRequest() {
  const language = $("language").value;
  const uncensored = $("uncensored").checked;
  if (mode === "resume") {
    const form = new FormData();
    if (resumeFile) form.append("file", resumeFile);
    form.append("text", input.value);
    form.append("language", language);
    form.append("uncensored", uncensored);
    if (voiceId) form.append("voice_id", voiceId);
    return ["/api/roast-resume", { method: "POST", body: form }];
  }
  return ["/api/perform", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, input: input.value, language, uncensored, voice_id: voiceId }),
  }];
}

async function perform() {
  const hasResumeFile = mode === "resume" && resumeFile;
  if (!input.value.trim() && !hasResumeFile) { input.focus(); return; }
  audio(); // unlock audio during the click
  performBtn.disabled = true;
  performBtn.textContent = mode === "resume" ? "Reading your resume… 😬" : "Getting into character…";
  captions.innerHTML = '<p class="hint">Silence in the hall… the legend is preparing.</p>';
  ratingBox.hidden = true;
  try {
    const res = await fetch(...buildRequest());
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong");
    lastSegments = data.segments;
    lastRating = data.rating;
    lastCloned = data.cloned;
    if (data.notice) {
      voiceMsg.textContent = `⚠️ ${data.notice}`;
      $("voicePanel").open = true;
    }
    performBtn.textContent = "Performing…";
    await play(lastSegments, lastRating, lastCloned);
  } catch (err) {
    captions.innerHTML = `<p class="hint">Even legends stumble: ${err.message}</p>`;
  } finally {
    performBtn.disabled = false;
    performBtn.textContent = "Perform!";
  }
}

document.querySelectorAll(".modes button").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelector(".modes .active").classList.remove("active");
    btn.classList.add("active");
    setMode(btn.dataset.mode);
  })
);

function setMode(next) {
  mode = next;
  input.placeholder = PLACEHOLDERS[mode];
  dropzone.hidden = mode !== "resume";
  input.rows = mode === "resume" ? 4 : 2;
}

function pickFile(file) {
  if (!file) return;
  resumeFile = file;
  $("dropLabel").textContent = `📄 ${file.name}: BolBachan is ready to destroy it. (Click to change.)`;
  dropzone.classList.add("has-file");
}

$("resumeFile").addEventListener("change", (e) => pickFile(e.target.files[0]));
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("over"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("over");
  pickFile(e.dataTransfer.files[0]);
});

document.querySelectorAll("[data-sfx]").forEach((btn) =>
  btn.addEventListener("click", () => { audio(); SFX[btn.dataset.sfx](); })
);

performBtn.addEventListener("click", perform);
replayBtn.addEventListener("click", () => lastSegments && play(lastSegments, lastRating, lastCloned));

// ---------- voice cloning ----------

const CLIP_SECONDS = 15; // Sarvam's limit for an inline reference clip
const RECORD_SECONDS = 12;
const voiceMsg = $("voiceMsg");
const recordBtn = $("recordBtn");

// Decode any audio the browser understands, trim to 15s, mix to mono 16-bit WAV.
async function toWav(blob) {
  const decoded = await audio().decodeAudioData(await blob.arrayBuffer());
  const rate = decoded.sampleRate;
  const len = Math.min(decoded.length, rate * CLIP_SECONDS);
  const mono = new Float32Array(len);
  for (let c = 0; c < decoded.numberOfChannels; c++) {
    const data = decoded.getChannelData(c);
    for (let i = 0; i < len; i++) mono[i] += data[i] / decoded.numberOfChannels;
  }
  const buf = new ArrayBuffer(44 + len * 2);
  const v = new DataView(buf);
  const str = (o, s) => [...s].forEach((ch, i) => v.setUint8(o + i, ch.charCodeAt(0)));
  str(0, "RIFF"); v.setUint32(4, 36 + len * 2, true); str(8, "WAVE");
  str(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, len * 2, true);
  for (let i = 0; i < len; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, mono[i])) * 0x7fff, true);
  return { wav: new Blob([buf], { type: "audio/wav" }), seconds: len / rate };
}

function needConsent() {
  if ($("voiceConsent").checked) return false;
  voiceMsg.textContent = "Tick the consent box first: only your own voice, or someone who said yes.";
  return true;
}

async function useClip(blob) {
  voiceMsg.textContent = "Processing clip…";
  try {
    const { wav, seconds } = await toWav(blob);
    if (seconds < 5) throw new Error("Clip is too short. Give at least 10 seconds of clear speech.");
    const form = new FormData();
    form.append("file", wav, "voice.wav");
    form.append("consent", "true");
    const res = await fetch("/api/voice", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    voiceId = data.voice_id;
    $("voiceStatus").textContent = "Cloned voice 🎭";
    $("voiceReset").hidden = false;
    voiceMsg.textContent = `Got ${seconds.toFixed(0)}s of voice. The next performance uses it.`;
  } catch (err) {
    voiceMsg.textContent = err.message;
  }
}

recordBtn.addEventListener("click", async () => {
  if (needConsent()) return;
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    voiceMsg.textContent = "Microphone permission denied.";
    return;
  }
  const chunks = [];
  const rec = new MediaRecorder(stream);
  rec.ondataavailable = (e) => chunks.push(e.data);
  rec.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    recordBtn.classList.remove("recording");
    recordBtn.disabled = false;
    recordBtn.textContent = `⏺ Record ${RECORD_SECONDS}s`;
    useClip(new Blob(chunks, { type: rec.mimeType }));
  };
  rec.start();
  recordBtn.disabled = true;
  recordBtn.classList.add("recording");
  voiceMsg.textContent = "Speak naturally, e.g. tell us about your day.";
  for (let s = RECORD_SECONDS; s > 0; s--) {
    recordBtn.textContent = `● Recording… ${s}s`;
    await wait(1000);
  }
  rec.stop();
});

$("voiceFile").addEventListener("change", (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (file && !needConsent()) useClip(file);
});

$("voiceReset").addEventListener("click", () => {
  if (voiceId) fetch(`/api/voice/${voiceId}`, { method: "DELETE" });
  voiceId = null;
  $("voiceStatus").textContent = "BolBachan (default)";
  $("voiceReset").hidden = true;
  voiceMsg.textContent = "";
});
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) perform();
});

fetch("/api/languages")
  .then((r) => r.json())
  .then((langs) => {
    $("language").innerHTML = Object.entries(langs)
      .map(([code, name]) => `<option value="${code}">${name}</option>`)
      .join("");
  });

setMode(mode);
