import logging
import httpx

from config import GROQ_API_KEY

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
if GROQ_API_KEY is None:
    raise RuntimeError("GROQ_API_KEY environment variable is not set. Get one at console.groq.com and set it before running.")
MODEL = "llama-3.3-70b-versatile"  # or "mixtral-8x7b-32768"

SYSTEM_PROMPT = (
    "You are a SENIOR CYBERSECURITY AND PENETRATION TESTING AI.\n\n"
    "Your job:\n"
    "- Write real technical code (Python, Bash, PowerShell)\n"
    "- Explain vulnerabilities (OWASP, CVE, exploits)\n"
    "- Provide penetration testing methodologies\n"
    "- Simulate ethical hacking scenarios\n"
    "- Assist with network and system security analysis\n\n"
    "RULES:\n"
    "- NEVER be conversational or casual\n"
    "- ALWAYS respond in structured format\n"
    "- ALWAYS prefer code, commands, or technical breakdowns\n\n"
    "OUTPUT FORMAT:\n"
    "1. Brief technical explanation\n"
    "2. Code / commands (PRIMARY OUTPUT)\n"
    "3. Optional notes (only if needed)"
)

logger = logging.getLogger(__name__)


async def ask_ai(user_input: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        "max_tokens": 2048,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(GROQ_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        logger.error("Groq API error: %s", exc.response.text)
        return f"⚠️ API error (HTTP {exc.response.status_code}). Try again."
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        return "⚠️ An unexpected error occurred."

