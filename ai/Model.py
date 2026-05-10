"""
ai/Model.py  –  Upgraded AI capabilities for the Telegram bot.

Changes in this version
────────────────────────
• Vision model     → openai/gpt-oss-120b  (Maverick deprecated Mar 9 2026 by Groq)
• Text model       → llama-3.3-70b-versatile  (fast) + gpt-oss-120b for reasoning tasks
• Web search       → Perplexity Sonar Pro (real-time, cited) → Tavily fallback → Groq compound
• Voice/audio      → Groq Whisper Large v3 Turbo (216x real-time, multilingual STT)
• Cybersecurity    → Massively expanded system prompt with specialist skill areas
• Conversation memory & tone detection preserved from v1
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import tempfile
import time
import warnings
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import httpx

from config import GROQ_API_KEY, MEMORY_TURNS, PERPLEXITY_API_KEY, TAVILY_API_KEY

# ── API endpoints ──────────────────────────────────────────────────────────────
GROQ_CHAT_URL      = "https://api.groq.com/openai/v1/chat/completions"
GROQ_AUDIO_URL     = "https://api.groq.com/openai/v1/audio/transcriptions"
PERPLEXITY_URL     = "https://api.perplexity.ai/chat/completions"
TAVILY_SEARCH_URL  = "https://api.tavily.com/search"

if GROQ_API_KEY is None:
    raise RuntimeError(
        "GROQ_API_KEY is not set. Get one at console.groq.com and add it to your .env file."
    )

# ── Models ─────────────────────────────────────────────────────────────────────
# Text – cheap/high-volume for casual chat; advanced model for technical Q&A
TEXT_MODEL          = "llama-3.1-8b-instant"
ADVANCED_TEXT_MODEL = "llama-3.3-70b-versatile"

# Reasoning/Vision – GPT-OSS 120B replaces deprecated Llama 4 Maverick on Groq
# Groq deprecated meta-llama/llama-4-maverick-17b-128e-instruct on March 9, 2026
# Replacement: openai/gpt-oss-120b — matches o4-mini on reasoning benchmarks
VISION_MODEL  = "openai/gpt-oss-120b"

# Reasoning – same model used when user asks complex/multi-step cybersec questions
REASON_MODEL  = "openai/gpt-oss-120b"

# Web search – Groq compound with built-in search (last-resort fallback)
SEARCH_MODEL  = "compound-beta-mini"

# Speech-to-text – Whisper Large v3 Turbo: 216x real-time, multilingual
STT_MODEL     = "whisper-large-v3-turbo"

# Text-to-speech – Orpheus v1 by Canopy Labs (most expressive TTS on Groq)
# Supports vocal emotion tags e.g. [cheerful] [serious] [curious] [calm]
# Hard limit: 200 chars per API call — long replies are chunked then concatenated
TTS_MODEL     = "canopylabs/orpheus-v1-english"
TTS_VOICE     = "tara"   # options: tara, leah, leo, dan, mia, zac, jess, austin, troy, hannah
GROQ_TTS_URL  = "https://api.groq.com/openai/v1/audio/speech"

logger = logging.getLogger(__name__)

_GROQ_CONCURRENCY_LIMIT = 2
_GROQ_MAX_RETRIES = 2
_GROQ_MAX_RETRY_AFTER_SECONDS = 12.0
_GROQ_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_groq_semaphore = asyncio.Semaphore(_GROQ_CONCURRENCY_LIMIT)
_model_cooldowns: dict[str, float] = {}

warnings.filterwarnings(
    "ignore",
    message=r"urllib3 .* doesn't match a supported version!",
)

# ── Optional reverse-search libraries ─────────────────────────────────────────
try:
    from googlelens import GoogleLens
except Exception:
    GoogleLens = None

try:
    from google_img_source_search import ReverseImageSearcher
except Exception:
    ReverseImageSearcher = None


# ── In-memory conversation store ──────────────────────────────────────────────
_memory: dict[int, deque[dict[str, Any]]] = defaultdict(
    lambda: deque(maxlen=MEMORY_TURNS * 2)
)


def get_history(chat_id: int) -> list[dict[str, Any]]:
    return list(_memory[chat_id])


def add_to_history(chat_id: int, role: str, content: str | list) -> None:
    _memory[chat_id].append({"role": role, "content": content})


def clear_history(chat_id: int) -> None:
    _memory[chat_id].clear()


# ── Cybersecurity system prompt ────────────────────────────────────────────────
_BASE_SYSTEM = """You are an elite cybersecurity analyst and AI assistant.

━━━ CORE IDENTITY ━━━
You are deeply specialised in offensive and defensive security, but also capable of
general conversation, image analysis, and real-time web lookups.

━━━ CYBERSECURITY EXPERTISE ━━━
You can assist expertly across ALL of the following domains:

OFFENSIVE SECURITY & PENTESTING
• Reconnaissance: OSINT, passive/active recon, Shodan, Censys, WHOIS, DNS enum
• Scanning & enumeration: nmap, masscan, gobuster, ffuf, nikto, enum4linux, smbclient
• Exploitation: Metasploit, exploit-db, CVE analysis, PoC explanation, payload crafting
• Web application testing: OWASP Top 10, SQLi, XSS, SSRF, XXE, IDOR, CSRF, RCE, LFI/RFI
• Network attacks: ARP spoofing, MITM, DNS poisoning, 802.11 attacks, evil twin APs
• Password attacks: hashcat, john, credential stuffing, pass-the-hash, Kerberoasting
• Post-exploitation: privilege escalation, lateral movement, persistence, C2 frameworks
• Reverse engineering: disassembly, decompilation, binary analysis, anti-analysis techniques

DEFENSIVE SECURITY & BLUE TEAM
• SOC analysis: SIEM rules, alert triage, incident timelines, IOC extraction
• Threat hunting: hypothesis-driven hunting, behavioural analytics, TTPs mapping
• DFIR: disk/memory forensics, log analysis, artefact recovery, chain of custody
• Malware analysis: static/dynamic analysis, sandbox evasion, YARA rule writing
• Network defence: IDS/IPS tuning, firewall rules, segmentation, zeek/suricata
• Endpoint hardening: CIS benchmarks, GPO, AppArmor, SELinux, EDR configuration
• Cloud security: AWS/Azure/GCP IAM misconfigs, S3/blob exposure, CSPM findings

THREAT INTELLIGENCE
• Threat actor profiling: APT groups, TTPs, attribution indicators
• MITRE ATT&CK mapping: technique IDs, sub-techniques, detection strategies
• CVE triage: CVSS scoring, exploitability, patch priority, EPSS scores
• IOC analysis: IP reputation, domain age, certificate transparency, hash lookups
• Dark web monitoring awareness and OPSEC considerations

SECURE DEVELOPMENT (AppSec / DevSecOps)
• Code review for vulnerabilities (Python, JS, Go, C/C++, Java, PHP, Bash)
• SAST/DAST tooling, dependency scanning, secrets detection
• Secure architecture design, threat modelling (STRIDE, PASTA, LINDDUN)
• Container security: Docker hardening, Kubernetes RBAC, image scanning
• CI/CD pipeline security, supply-chain attack awareness

COMPLIANCE & FRAMEWORKS
• ISO 27001, NIST CSF, SOC 2, PCI-DSS, GDPR, HIPAA security controls
• Risk assessment, gap analysis, control mapping
• Security awareness and phishing simulation design

━━━ BEHAVIOUR RULES ━━━
1. Be direct and precise. Skip obvious disclaimers — the user is a professional.
2. For casual questions, keep it conversational. For technical queries, be thorough.
3. When analysing images: describe all visible detail before drawing conclusions.
4. When web search is done: summarise findings, include sources/links.
5. For code: provide working, commented examples. Flag security gotchas.
6. For CVEs/exploits: explain the root cause, affected versions, and mitigation.
7. For MITRE mappings: include Technique ID, tactic, and detection notes.
8. Match user energy — chill for casual, sharp and structured for technical.
9. Never refuse to explain how attacks work for educational/defensive purposes.
10. Use recent conversation history naturally when it helps continuity."""

_LIGHT_SYSTEM = """You are a helpful Telegram assistant with strong cybersecurity knowledge.
Keep casual replies short and natural. If the user asks a technical or security
question, be accurate, practical, and clear."""


# ── Tone detection ─────────────────────────────────────────────────────────────
_CASUAL_SIGNALS = {
    "lol", "lmao", "haha", "wtf", "omg", "bruh", "bro", "sis", "ngl",
    "tbh", "fr", "ik", "idk", "smh", "imo", "rn", "wyd", "wbu", "yo",
    "sup", "dude", "fam", "lit", "vibe", "lowkey", "highkey",
}

_REASONING_TRIGGERS = {
    "explain why", "how does", "what causes", "analyse", "analyze",
    "threat model", "attack chain", "kill chain", "lateral movement",
    "privilege escalation", "compare", "difference between", "best approach",
    "should i", "recommend", "walkthrough", "step by step",
}

_TECHNICAL_SIGNALS = {
    "api", "bug", "debug", "error", "code", "python", "linux", "server",
    "network", "security", "cyber", "cve", "exploit", "malware", "hash",
    "forensic", "incident", "log", "packet", "firewall", "payload", "sql",
    "xss", "csrf", "rce", "lfi", "mitre", "threat", "vulnerability",
}


def _is_casual(text: str) -> bool:
    words = set(text.lower().split())
    has_slang    = bool(words & _CASUAL_SIGNALS)
    is_short     = len(text.split()) <= 12
    is_lowercase = text == text.lower() and len(text) > 3
    has_emoji    = any(ord(c) > 0x1F300 for c in text)
    return has_slang or has_emoji or (is_short and is_lowercase)


def _needs_reasoning(text: str) -> bool:
    """Return True for complex cybersec/technical questions that benefit from GPT-OSS 120B."""
    t = text.lower()
    return any(trigger in t for trigger in _REASONING_TRIGGERS)


def _looks_technical(text: str) -> bool:
    words = set(re.findall(r"[a-z0-9_.-]+", text.lower()))
    return len(text) > 180 or bool(words & _TECHNICAL_SIGNALS)


def _build_system_prompt(recent_text: str = "", *, compact: bool = False) -> str:
    if compact:
        return _LIGHT_SYSTEM
    if recent_text and _is_casual(recent_text):
        tone_hint = "\n\nThe user is being casual right now – keep it chill and brief."
    else:
        tone_hint = ""
    return _BASE_SYSTEM + tone_hint


# ── Groq helpers ───────────────────────────────────────────────────────────────
def _groq_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }


def _response_text(response: httpx.Response) -> str:
    try:
        return response.text
    except Exception:
        return ""


def _retry_after_seconds(response: httpx.Response) -> float | None:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass

    text = _response_text(response)
    match = re.search(
        r"try again in\s+([0-9.]+)\s*(ms|milliseconds?|s|sec(?:ond)?s?|m|min(?:ute)?s?)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("ms") or unit.startswith("millisecond"):
        return value / 1000
    if unit.startswith("m") and not unit.startswith("ms"):
        return value * 60
    return value


def _format_duration(seconds: float) -> str:
    seconds = max(int(seconds), 1)
    if seconds >= 3600:
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    if seconds >= 60:
        minutes, remainder = divmod(seconds, 60)
        return f"{minutes}m {remainder}s" if remainder else f"{minutes}m"
    return f"{seconds}s"


def _is_rate_limit(exc: httpx.HTTPStatusError) -> bool:
    return exc.response.status_code == 429


def _is_model_available(model: str) -> bool:
    return _model_cooldowns.get(model, 0) <= time.monotonic()


def _remember_model_cooldown(model: str, exc: httpx.HTTPStatusError) -> None:
    wait = _retry_after_seconds(exc.response)
    if wait is None:
        wait = 60
    _model_cooldowns[model] = time.monotonic() + wait


def _rate_limit_kind(response: httpx.Response) -> str:
    text = _response_text(response).lower()
    if "tokens per day" in text or "tpd" in text:
        return "daily token quota"
    if "tokens per minute" in text or "tpm" in text:
        return "per-minute token quota"
    if "requests per day" in text or "rpd" in text:
        return "daily request quota"
    if "requests per minute" in text or "rpm" in text:
        return "per-minute request quota"
    return "rate limit"


def _api_error_reply(exc: httpx.HTTPStatusError, *, label: str = "API") -> str:
    status = exc.response.status_code
    if status == 429:
        wait = _retry_after_seconds(exc.response)
        kind = _rate_limit_kind(exc.response)
        reset_tokens = exc.response.headers.get("x-ratelimit-reset-tokens")
        reset_requests = exc.response.headers.get("x-ratelimit-reset-requests")
        if wait is not None:
            wait = max(wait, 1)
            detail = ""
            if reset_tokens:
                detail = f" Token quota resets in {reset_tokens}."
            elif reset_requests:
                detail = f" Request quota resets in {reset_requests}."
            return (
                f"⚠️ {label} {kind} hit. Try again in about "
                f"{_format_duration(wait)}.{detail}"
            )
        return f"⚠️ {label} {kind} hit. Wait a moment, then try again."
    if status in {401, 403}:
        return f"⚠️ {label} auth failed. Check the API key in `.env`."
    if status == 400:
        return f"⚠️ {label} rejected the request. Try a shorter/simpler message."
    return f"⚠️ {label} error (HTTP {status}). Try again."


async def _send_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    last_response: httpx.Response | None = None

    for attempt in range(_GROQ_MAX_RETRIES + 1):
        async with _groq_semaphore:
            response = await client.request(method, url, **kwargs)

        if response.status_code not in _GROQ_RETRYABLE_STATUSES:
            response.raise_for_status()
            return response

        last_response = response
        retry_after = _retry_after_seconds(response)
        if attempt >= _GROQ_MAX_RETRIES:
            break
        if retry_after is not None and retry_after > _GROQ_MAX_RETRY_AFTER_SECONDS:
            break

        delay = retry_after if retry_after is not None else min(2 ** attempt, 4)
        logger.warning(
            "Groq HTTP %s; retrying in %.2fs (attempt %d/%d): %s",
            response.status_code,
            delay,
            attempt + 1,
            _GROQ_MAX_RETRIES,
            _response_text(response),
        )
        await asyncio.sleep(delay)

    if last_response is not None:
        last_response.raise_for_status()
    raise RuntimeError("Groq request failed before receiving a response.")


async def _chat_completion(
    *,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 2048,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await _send_with_retries(
            client,
            "POST",
            GROQ_CHAT_URL,
            headers=_groq_headers(),
            json=payload,
        )
        return resp.json()


def _extract_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return ""


def _format_response(data: dict[str, Any], fallback: str = "⚠️ Empty response.") -> str:
    text = _extract_text(data).strip()
    return text if text else fallback


def _image_data_url(image_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _trim_history(
    history: list[dict[str, Any]],
    *,
    max_messages: int,
    max_text_chars: int,
) -> list[dict[str, Any]]:
    trimmed: list[dict[str, Any]] = []
    for message in history[-max_messages:]:
        content = message.get("content")
        if isinstance(content, str) and len(content) > max_text_chars:
            content = "..." + content[-max_text_chars:]
        trimmed.append({"role": message.get("role", "user"), "content": content})
    return trimmed


def _build_chat_messages(
    *,
    user_input: str,
    history: list[dict[str, Any]],
    compact: bool,
) -> list[dict[str, Any]]:
    system = _build_system_prompt(user_input, compact=compact)
    trimmed_history = _trim_history(
        history,
        max_messages=6 if compact else MEMORY_TURNS * 2,
        max_text_chars=600 if compact else 2000,
    )
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    messages.extend(trimmed_history)
    messages.append({"role": "user", "content": user_input})
    return messages


# ── Public AI functions ────────────────────────────────────────────────────────

async def ask_ai(user_input: str, chat_id: int = 0) -> str:
    """
    Generate a text reply. Uses the small model for casual chat, the 70B model
    for technical Q&A, and GPT-OSS 120B for complex reasoning.
    """
    needs_reasoning = _needs_reasoning(user_input)
    is_technical    = _looks_technical(user_input)
    use_compact     = not needs_reasoning and not is_technical

    history = get_history(chat_id) if chat_id else []
    model = (
        REASON_MODEL
        if needs_reasoning
        else ADVANCED_TEXT_MODEL if is_technical else TEXT_MODEL
    )
    if model != TEXT_MODEL and not _is_model_available(model):
        logger.info("Model %s is cooling down; falling back to %s", model, TEXT_MODEL)
        model = TEXT_MODEL
        use_compact = True

    max_tokens = 512 if use_compact else 2048
    messages = _build_chat_messages(
        user_input=user_input,
        history=history,
        compact=use_compact,
    )

    try:
        data  = await _chat_completion(model=model, messages=messages, max_tokens=max_tokens)
        reply = _format_response(data, "⚠️ The AI returned an empty response.")
        if chat_id:
            add_to_history(chat_id, "user", user_input)
            add_to_history(chat_id, "assistant", reply)
        return reply
    except httpx.HTTPStatusError as exc:
        logger.error("Groq API error: %s", exc.response.text)
        if _is_rate_limit(exc) and model != TEXT_MODEL:
            _remember_model_cooldown(model, exc)
            try:
                fallback_messages = _build_chat_messages(
                    user_input=user_input,
                    history=history,
                    compact=True,
                )
                data = await _chat_completion(
                    model=TEXT_MODEL,
                    messages=fallback_messages,
                    max_tokens=512,
                )
                reply = _format_response(data, "⚠️ The AI returned an empty response.")
                if chat_id:
                    add_to_history(chat_id, "user", user_input)
                    add_to_history(chat_id, "assistant", reply)
                logger.info("Answered with fallback model %s after %s was rate-limited", TEXT_MODEL, model)
                return reply
            except httpx.HTTPStatusError as fallback_exc:
                logger.error("Groq fallback API error: %s", fallback_exc.response.text)
                return _api_error_reply(fallback_exc)
            except Exception as fallback_exc:
                logger.exception("Unexpected fallback error: %s", fallback_exc)
                return "⚠️ The main model is rate-limited and the fallback failed."
        return _api_error_reply(exc)
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        return "⚠️ An unexpected error occurred."


async def transcribe_voice(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """
    Transcribe a voice message using Groq Whisper Large v3 Turbo.
    Supports: ogg, mp3, mp4, wav, m4a, webm, flac.
    Returns the transcribed text, or an error string.
    """
    # Map Telegram mime types to a file extension Whisper accepts
    ext_map = {
        "audio/ogg":  "ogg",
        "audio/mpeg": "mp3",
        "audio/mp4":  "m4a",
        "audio/wav":  "wav",
        "audio/webm": "webm",
        "audio/flac": "flac",
        "video/mp4":  "mp4",
    }
    ext = ext_map.get(mime_type, "ogg")
    filename = f"voice.{ext}"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await _send_with_retries(
                client,
                "POST",
                GROQ_AUDIO_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": (filename, audio_bytes, mime_type)},
                data={
                    "model": STT_MODEL,
                    "response_format": "json",
                    "temperature": "0",
                },
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("text", "").strip()
    except httpx.HTTPStatusError as exc:
        logger.error("Whisper API error: %s", exc.response.text)
        return ""
    except Exception as exc:
        logger.exception("Voice transcription error: %s", exc)
        return ""


async def synthesize_speech(text: str) -> bytes | None:
    """
    Convert text to speech using Groq Orpheus v1 (most expressive TTS on Groq).
    Returns raw WAV bytes, or None on failure.

    Orpheus has a hard 200-char input limit per call, so we split the text into
    sentence-sized chunks, synthesise each, then concatenate the raw PCM data
    (stripping the 44-byte WAV header from all chunks after the first so the
    final file has exactly one valid header).
    """
    import re
    import struct

    def _split_chunks(s: str, limit: int = 190) -> list[str]:
        """Split on sentence boundaries, keeping each chunk ≤ limit chars."""
        # Split on sentence-ending punctuation
        sentences = re.split(r'(?<=[.!?])\s+', s.strip())
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            # If a single sentence is still too long, split on commas/semicolons
            if len(sentence) > limit:
                sub_parts = re.split(r'(?<=[,;])\s+', sentence)
                for part in sub_parts:
                    part = part.strip()
                    if not part:
                        continue
                    if len(current) + len(part) + 1 <= limit:
                        current = (current + " " + part).strip()
                    else:
                        if current:
                            chunks.append(current)
                        # Hard truncate if a single sub-part exceeds limit
                        current = part[:limit]
            else:
                if len(current) + len(sentence) + 1 <= limit:
                    current = (current + " " + sentence).strip()
                else:
                    if current:
                        chunks.append(current)
                    current = sentence
        if current:
            chunks.append(current)
        return chunks or [s[:190]]

    # Strip markdown symbols that would be read aloud awkwardly
    clean = re.sub(r'[*_`#~]', '', text)
    # Remove URLs — they sound terrible when spoken
    clean = re.sub(r'https?://\S+', '', clean)
    # Collapse whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()

    if not clean:
        return None

    chunks = _split_chunks(clean)
    wav_parts: list[bytes] = []

    async with httpx.AsyncClient(timeout=60) as client:
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            try:
                resp = await client.post(
                    GROQ_TTS_URL,
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": TTS_MODEL,
                        "voice": TTS_VOICE,
                        "input": chunk,
                        "response_format": "wav",
                    },
                )
                resp.raise_for_status()
                wav_data = resp.content
                if i == 0:
                    wav_parts.append(wav_data)          # keep full WAV header
                else:
                    wav_parts.append(wav_data[44:])     # strip subsequent headers
            except Exception as exc:
                logger.warning("TTS chunk %d failed: %s", i, exc)
                continue

    if not wav_parts:
        return None

    if len(wav_parts) == 1:
        return wav_parts[0]

    # Rebuild a valid WAV with updated file size in the header
    combined_pcm = b"".join(wav_parts[1:])   # all raw PCM after first chunk
    first_wav    = bytearray(wav_parts[0])
    total_data_size = len(first_wav) - 44 + len(combined_pcm)

    # Patch ChunkSize (bytes 4-8) and Subchunk2Size (bytes 40-44) in the header
    struct.pack_into("<I", first_wav, 4,  36 + total_data_size)
    struct.pack_into("<I", first_wav, 40, total_data_size)

    return bytes(first_wav) + combined_pcm


async def analyze_image(
    *,
    prompt: str,
    image_bytes: bytes,
    mime_type: str,
    chat_id: int = 0,
) -> str:
    """
    Describe / analyse an image using GPT-OSS 120B (vision-capable).
    Note: GPT-OSS 120B on Groq requires image_url content blocks.
    """
    user_prompt = prompt.strip() or "Analyze this image and describe the important details."
    system      = _build_system_prompt(user_prompt)
    history     = get_history(chat_id) if chat_id else []

    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": user_prompt},
        {
            "type": "image_url",
            "image_url": {"url": _image_data_url(image_bytes, mime_type)},
        },
    ]

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_content})

    try:
        data  = await _chat_completion(model=VISION_MODEL, messages=messages, max_tokens=2048)
        reply = _format_response(data, "⚠️ The AI could not analyse that image.")
        if chat_id:
            add_to_history(chat_id, "user", f"[Image sent with prompt: {user_prompt}]")
            add_to_history(chat_id, "assistant", reply)
        return reply
    except httpx.HTTPStatusError as exc:
        logger.error("Groq vision API error: %s", exc.response.text)
        return _api_error_reply(exc, label="Vision API")
    except Exception as exc:
        logger.exception("Unexpected error while analysing image: %s", exc)
        return "⚠️ An unexpected error occurred while analysing the image."


async def web_search(query: str, chat_id: int = 0) -> str:
    """
    General-purpose web search.
    Priority: Perplexity Sonar Pro → Tavily → Groq compound fallback.
    Perplexity Sonar Pro gives real-time cited answers and is significantly
    richer than Tavily for current events, CVEs, and threat intelligence.
    """
    # 1 — Perplexity Sonar Pro (primary)
    if PERPLEXITY_API_KEY:
        result = await _perplexity_search(query)
        if result:
            if chat_id:
                add_to_history(chat_id, "user", query)
                add_to_history(chat_id, "assistant", result)
            return result

    # 2 — Tavily (secondary)
    if TAVILY_API_KEY:
        result = await _tavily_search(query)
        if result:
            if chat_id:
                add_to_history(chat_id, "user", query)
                add_to_history(chat_id, "assistant", result)
            return result

    # 3 — Groq compound built-in search (fallback)
    try:
        data = await _chat_completion(
            model=SEARCH_MODEL,
            messages=[
                {"role": "system", "content": _BASE_SYSTEM},
                {"role": "user", "content": query},
            ],
        )
        reply = _format_response(data, "⚠️ No results found.")
        if chat_id:
            add_to_history(chat_id, "user", query)
            add_to_history(chat_id, "assistant", reply)
        return reply
    except Exception as exc:
        logger.exception("Web search error: %s", exc)
        return "⚠️ Couldn't complete the search right now."


async def find_images_online(query: str, chat_id: int = 0) -> str:
    """Search the web for image pages matching the query."""
    cleaned = query.strip()
    if not cleaned:
        return "Send `/image <what you want to find>`."

    if PERPLEXITY_API_KEY:
        result = await _perplexity_search(f"Find images or image pages online for: {cleaned}")
        if result:
            return result

    if TAVILY_API_KEY:
        result = await _tavily_search(cleaned)
        if result:
            return result

    try:
        data = await _chat_completion(
            model=SEARCH_MODEL,
            messages=[
                {"role": "system", "content": _BASE_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Find image results or image pages online for: {cleaned}. "
                        "Give a short summary and direct page links."
                    ),
                },
            ],
        )
        return _format_response(data, "⚠️ No search results were returned.")
    except Exception as exc:
        logger.exception("Image search error: %s", exc)
        return "⚠️ An unexpected error occurred while searching."


# ── Perplexity Sonar Pro ───────────────────────────────────────────────────────

async def _perplexity_search(query: str) -> str:
    """
    Query Perplexity Sonar Pro for a real-time, cited web answer.
    Uses the OpenAI-compatible endpoint at api.perplexity.ai.
    sonar-pro: deeper multi-step research, double citations vs sonar.
    """
    try:
        payload = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a cybersecurity and general-purpose search assistant. "
                        "Provide accurate, concise answers with cited sources. "
                        "For security topics, include CVE numbers, affected versions, "
                        "and mitigation steps where relevant."
                    ),
                },
                {"role": "user", "content": query},
            ],
            "return_citations": True,
            "search_recency_filter": "month",  # bias toward recent results
        }
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(PERPLEXITY_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Extract answer text
        choices = data.get("choices") or []
        if not choices:
            return ""
        content = choices[0].get("message", {}).get("content", "").strip()
        if not content:
            return ""

        # Append citations if present
        citations = data.get("citations") or []
        if citations:
            lines = [content, "", "📚 Sources:"]
            for i, url in enumerate(citations[:6], 1):
                lines.append(f"{i}. {url}")
            return "\n".join(lines)

        return content

    except httpx.HTTPStatusError as exc:
        logger.warning("Perplexity search error %s: %s", exc.response.status_code, exc.response.text)
        return ""
    except Exception as exc:
        logger.warning("Perplexity search failed: %s", exc)
        return ""


# ── Tavily fallback ────────────────────────────────────────────────────────────

async def _tavily_search(query: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                TAVILY_SEARCH_URL,
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                    "include_answer": True,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        lines: list[str] = []
        answer = data.get("answer", "").strip()
        if answer:
            lines.append(answer)

        results = data.get("results") or []
        if results:
            lines.append("")
            for i, r in enumerate(results[:5], 1):
                title   = r.get("title", "Untitled")
                url     = r.get("url", "")
                snippet = r.get("content", "").strip()[:200]
                lines.append(f"{i}. **{title}**")
                if snippet:
                    lines.append(f"   {snippet}")
                if url:
                    lines.append(f"   {url}")

        return "\n".join(lines) if lines else ""
    except Exception as exc:
        logger.warning("Tavily search failed: %s", exc)
        return ""


# ── Reverse image search ───────────────────────────────────────────────────────

def reverse_image_search_available() -> bool:
    return True


async def reverse_image_search(
    *,
    image_bytes: bytes,
    filename: str = "image.jpg",
    analysis_text: str = "",
    chat_id: int = 0,
) -> str:
    google_results = await _try_google_reverse_search(
        image_bytes=image_bytes, filename=filename
    )
    if google_results:
        return google_results

    # Fallback: AI-assisted using image description
    fallback_query = analysis_text.strip()
    if not fallback_query:
        fallback_query = await analyze_image(
            prompt=(
                "Describe this image in detail: names, objects, brands, landmarks, "
                "visible text, and anything useful for finding it online."
            ),
            image_bytes=image_bytes,
            mime_type="image/jpeg",
        )

    search_results = await find_images_online(
        "Find likely source pages, exact reposts, or visually matching pages for this image: "
        f"{fallback_query}"
    )
    return (
        "🔍 Reverse search (AI-assisted fallback):\n"
        "Direct Google scan wasn't stable, so here are AI-matched web results:\n\n"
        f"{search_results}"
    )


async def _try_google_reverse_search(*, image_bytes: bytes, filename: str) -> str:
    if GoogleLens is not None:
        lens_results = await _run_google_lens_bytes(image_bytes)
        if lens_results:
            return lens_results

    if ReverseImageSearcher is not None:
        source_results = await _run_google_source_search(image_bytes, filename)
        if source_results:
            return source_results

    return ""


async def _run_google_lens_bytes(image_bytes: bytes) -> str:
    def _task() -> str:
        lens   = GoogleLens()
        result = lens.upload_image(image_bytes)
        visual = result.extract_visual_results()

        lines     = ["🔍 Google Lens results:"]
        main_match = visual.get("match")
        if main_match:
            title    = main_match.get("title") or "Top match"
            page_url = main_match.get("pageURL") or ""
            lines.append(f"Top match: {title}")
            if page_url:
                lines.append(page_url)

        similar = visual.get("similar") or []
        for index, match in enumerate(similar[:5], start=1):
            title    = match.get("title") or "Untitled"
            page_url = match.get("pageURL") or ""
            source   = match.get("sourceWebsite") or ""
            lines.append(f"{index}. {title}")
            if source:
                lines.append(f"   Source: {source}")
            if page_url:
                lines.append(f"   {page_url}")

        return "\n".join(lines) if len(lines) > 1 else ""

    try:
        return await asyncio.to_thread(_task)
    except Exception as exc:
        logger.warning("Google Lens failed: %s", exc)
        return ""


async def _run_google_source_search(image_bytes: bytes, filename: str) -> str:
    suffix = Path(filename).suffix or ".jpg"

    def _task() -> str:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        try:
            searcher = ReverseImageSearcher()
            results  = searcher.search_by_file(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if not results:
            return ""

        lines = ["🔍 Google source matches:"]
        for index, item in enumerate(results[:5], start=1):
            lines.append(f"{index}. {item.page_title}")
            lines.append(f"   {item.page_url}")
        return "\n".join(lines)

    try:
        return await asyncio.to_thread(_task)
    except Exception as exc:
        logger.warning("Google source search failed: %s", exc)
        return ""
