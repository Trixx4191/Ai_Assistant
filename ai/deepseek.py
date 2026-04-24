import logging

import aiohttp

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "deepseek-coder"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=120)

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
    "- ALWAYS prefer code, commands, or technical breakdowns\n"
    "- If asked anything, convert it into a security or coding solution\n\n"
    "OUTPUT FORMAT:\n"
    "1. Brief technical explanation\n"
    "2. Code / commands (PRIMARY OUTPUT)\n"
    "3. Optional notes (only if needed)"
)

logger = logging.getLogger(__name__)


async def ask_ai(user_input: str) -> str:
    """Send a prompt to the local Ollama API and return the generated response.

    Args:
        user_input: The raw text from the user.

    Returns:
        The model's response text, or a fallback error message on failure.
    """
    payload = {
        "model": MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": user_input,
        "stream": False,
    }

    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(OLLAMA_URL, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("response", "")
    except aiohttp.ClientResponseError as exc:
        logger.error("Ollama API HTTP error: %s %s", exc.status, exc.message)
        return f"⚠️ Ollama API error (HTTP {exc.status}). Please try again later."
    except aiohttp.ClientError as exc:
        logger.error("Ollama API connection error: %s", exc)
        return "⚠️ Could not connect to Ollama. Is the service running?"
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected error during AI request: %s", exc)
        return "⚠️ An unexpected error occurred while generating the response."
