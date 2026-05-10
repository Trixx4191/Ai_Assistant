"""
cli.py - Interactive terminal client for the AI assistant.

Run:
    python cli.py
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import mimetypes
import shlex
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Awaitable, Callable

from ai.Model import (
    ADVANCED_TEXT_MODEL,
    REASON_MODEL,
    TEXT_MODEL,
    analyze_image,
    ask_ai,
    clear_history,
    find_images_online,
    transcribe_voice,
    web_search,
)

COMMANDS = (
    "/help",
    "/clear",
    "/search",
    "/image",
    "/vision",
    "/read",
    "/transcribe",
    "/cve",
    "/exploit",
    "/mitre",
    "/hash",
    "/models",
    "/exit",
)

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


CLI_CHAT_ID = -1001


class UI:
    def __init__(self, *, plain: bool = False) -> None:
        self.plain = plain or not sys.stdout.isatty()

    def color(self, text: str, code: str) -> str:
        if self.plain:
            return text
        return f"\033[{code}m{text}\033[0m"

    def dim(self, text: str) -> str:
        return self.color(text, "2")

    def cyan(self, text: str) -> str:
        return self.color(text, "36")

    def green(self, text: str) -> str:
        return self.color(text, "32")

    def magenta(self, text: str) -> str:
        return self.color(text, "35")

    def yellow(self, text: str) -> str:
        return self.color(text, "33")

    def red(self, text: str) -> str:
        return self.color(text, "31")

    def bold(self, text: str) -> str:
        return self.color(text, "1")

    def line(self, text: str = "") -> None:
        print(text)


def _terminal_width() -> int:
    return max(shutil.get_terminal_size((88, 20)).columns, 60)


def _banner(ui: UI) -> None:
    width = min(_terminal_width(), 92)
    title = " SHA0-1 AI CLI "
    rule = "=" * width
    ui.line(ui.cyan(rule))
    ui.line(ui.bold(title.center(width)))
    ui.line(ui.dim("Interactive terminal mode. Type /help for commands, /exit to quit.".center(width)))
    ui.line(ui.cyan(rule))


def _help(ui: UI) -> None:
    commands = [
        ("/help", "Show this command list"),
        ("/clear", "Clear this CLI conversation memory"),
        ("/search <query>", "Live web search with configured search providers"),
        ("/image <query>", "Find image pages online"),
        ("/vision <path> [prompt]", "Analyze an image from disk"),
        ("/read <path> [prompt]", "Read a PDF/text file and ask about it"),
        ("/transcribe <path>", "Transcribe an audio file with Groq Whisper"),
        ("/cve <CVE-ID>", "Look up CVE details and mitigations"),
        ("/exploit <term>", "Search for exploits and PoCs"),
        ("/mitre <technique>", "Explain a MITRE ATT&CK technique"),
        ("/hash <hash>", "Check hash reputation via search"),
        ("/models", "Show model routing"),
        ("/exit", "Quit"),
    ]
    ui.line(ui.bold("\nCommands"))
    for name, desc in commands:
        ui.line(f"  {ui.cyan(name.ljust(28))} {desc}")
    ui.line()


def _setup_readline() -> None:
    if not sys.stdin.isatty():
        return
    try:
        import readline
    except Exception:
        return

    def complete(text: str, state: int) -> str | None:
        matches = [command for command in COMMANDS if command.startswith(text)]
        if state < len(matches):
            return matches[state] + " "
        return None

    readline.set_completer(complete)
    readline.parse_and_bind("tab: complete")


def _models(ui: UI) -> None:
    ui.line(ui.bold("\nModel routing"))
    ui.line(f"  Casual/simple chat     -> {ui.green(TEXT_MODEL)}")
    ui.line(f"  Technical questions    -> {ui.green(ADVANCED_TEXT_MODEL)}")
    ui.line(f"  Reasoning-heavy tasks  -> {ui.green(REASON_MODEL)}")
    ui.line("  Rate-limited large model -> automatic fallback to the small chat model")
    ui.line()


def _render(text: str, ui: UI) -> None:
    width = _terminal_width()
    in_code = False
    ui.line(ui.magenta("\nAI"))
    for raw_line in text.splitlines() or [""]:
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            ui.line(ui.dim(line))
            continue
        if in_code or not line:
            ui.line(line)
            continue
        wrapped = textwrap.wrap(
            line,
            width=max(width - 4, 56),
            replace_whitespace=False,
            drop_whitespace=False,
        )
        for part in wrapped or [""]:
            ui.line(part)
    ui.line()


async def _spinner(label: str, done: asyncio.Event, ui: UI) -> None:
    if ui.plain:
        return
    frames = ("|", "/", "-", "\\")
    index = 0
    while not done.is_set():
        sys.stdout.write(f"\r{ui.yellow(frames[index % len(frames)])} {label}")
        sys.stdout.flush()
        index += 1
        try:
            await asyncio.wait_for(done.wait(), timeout=0.12)
        except asyncio.TimeoutError:
            pass
    sys.stdout.write("\r" + " " * (len(label) + 4) + "\r")
    sys.stdout.flush()


async def _run_with_spinner(label: str, ui: UI, work: Awaitable[str]) -> str:
    done = asyncio.Event()
    spinner_task = asyncio.create_task(_spinner(label, done, ui))
    try:
        return await work
    finally:
        done.set()
        await spinner_task


def _split_command(text: str) -> tuple[str, list[str]]:
    try:
        parts = shlex.split(text)
    except ValueError as exc:
        return text.split(maxsplit=1)[0], [str(exc)]
    if not parts:
        return "", []
    return parts[0].lower(), parts[1:]


def _read_document(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type == "application/pdf":
        if PdfReader is None:
            raise RuntimeError("PDF support needs pypdf installed.")
        reader = PdfReader(str(path))
        pages: list[str] = []
        for page in reader.pages[:12]:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())
        return "\n\n".join(pages)[:12000]
    return path.read_text(errors="ignore")[:12000]


def _mime_or_default(path: Path, default: str) -> str:
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type or default


async def _handle_file_command(
    *,
    args: list[str],
    ui: UI,
    action: Callable[[Path, str], Awaitable[str]],
    default_prompt: str,
    label: str,
) -> str:
    if not args:
        return f"Usage: /{label} <path> [prompt]"
    path = Path(args[0]).expanduser()
    if not path.exists() or not path.is_file():
        return f"File not found: {path}"
    prompt = " ".join(args[1:]).strip() or default_prompt
    return await action(path, prompt)


async def _handle_command(text: str, ui: UI) -> str | None:
    command, args = _split_command(text)

    if command in {"/exit", "/quit", ":q"}:
        raise EOFError
    if command == "/help":
        _help(ui)
        return None
    if command == "/models":
        _models(ui)
        return None
    if command == "/clear":
        clear_history(CLI_CHAT_ID)
        return "CLI memory cleared."
    if command == "/search":
        query = " ".join(args).strip()
        return "Usage: /search <query>" if not query else await web_search(query, chat_id=CLI_CHAT_ID)
    if command == "/image":
        query = " ".join(args).strip()
        return "Usage: /image <query>" if not query else await find_images_online(query, chat_id=CLI_CHAT_ID)
    if command == "/cve":
        cve_id = " ".join(args).strip()
        if not cve_id:
            return "Usage: /cve CVE-2024-1234"
        query = (
            f"Look up {cve_id}: provide the vulnerability description, CVSS score, "
            "affected products and versions, exploit availability, and recommended mitigations."
        )
        return await web_search(query, chat_id=CLI_CHAT_ID)
    if command == "/exploit":
        term = " ".join(args).strip()
        if not term:
            return "Usage: /exploit <service/CVE/software>"
        query = (
            f"Find public exploits, proof-of-concept code, and Metasploit modules for: {term}. "
            "Include exploit-db IDs, GitHub links, and any relevant CVEs."
        )
        return await web_search(query, chat_id=CLI_CHAT_ID)
    if command == "/mitre":
        technique = " ".join(args).strip()
        if not technique:
            return "Usage: /mitre T1059"
        query = (
            f"Look up MITRE ATT&CK technique: {technique}. Provide the technique ID, tactic, "
            "description, real-world usage examples, detection methods, and mitigations."
        )
        return await ask_ai(query, chat_id=CLI_CHAT_ID)
    if command == "/hash":
        hash_value = " ".join(args).strip()
        if not hash_value:
            return "Usage: /hash <MD5/SHA1/SHA256>"
        query = (
            f"Check the reputation of this file hash: {hash_value}. Search VirusTotal, "
            "MalwareBazaar, and threat intelligence sources. Is it known malware?"
        )
        return await web_search(query, chat_id=CLI_CHAT_ID)
    if command == "/vision":
        async def vision_action(path: Path, prompt: str) -> str:
            return await analyze_image(
                prompt=prompt,
                image_bytes=path.read_bytes(),
                mime_type=_mime_or_default(path, "image/jpeg"),
                chat_id=CLI_CHAT_ID,
            )

        return await _handle_file_command(
            args=args,
            ui=ui,
            action=vision_action,
            default_prompt="Analyze this image and describe the important details.",
            label="vision",
        )
    if command == "/read":
        async def read_action(path: Path, prompt: str) -> str:
            document = _read_document(path)
            if not document.strip():
                return "I could not extract text from that file."
            request = f"{prompt}\n\n--- FILE: {path.name} ---\n{document}"
            return await ask_ai(request, chat_id=CLI_CHAT_ID)

        return await _handle_file_command(
            args=args,
            ui=ui,
            action=read_action,
            default_prompt="Summarize this file and call out the most important details.",
            label="read",
        )
    if command == "/transcribe":
        if not args:
            return "Usage: /transcribe <audio-path>"
        path = Path(args[0]).expanduser()
        if not path.exists() or not path.is_file():
            return f"File not found: {path}"
        return await transcribe_voice(path.read_bytes(), _mime_or_default(path, "audio/ogg"))

    return f"Unknown command: {command}. Type /help."


async def _chat_loop(ui: UI) -> None:
    _banner(ui)
    _models(ui)
    while True:
        try:
            prompt = ui.green("you") + ui.dim(" > ")
            user_input = await _read_input(prompt)
        except (EOFError, KeyboardInterrupt):
            ui.line(ui.dim("\nbye."))
            return

        user_input = user_input.strip()
        if not user_input:
            continue

        try:
            if user_input.startswith("/"):
                result = await _run_with_spinner(
                    "working...",
                    ui,
                    _handle_command(user_input, ui),
                )
            else:
                result = await _run_with_spinner(
                    "thinking...",
                    ui,
                    ask_ai(user_input, chat_id=CLI_CHAT_ID),
                )
        except EOFError:
            ui.line(ui.dim("\nbye."))
            return
        except Exception as exc:
            logging.exception("CLI command failed")
            result = f"Something went wrong: {exc}"

        if result:
            _render(result, ui)


async def _read_input(prompt: str) -> str:
    if sys.stdin.isatty():
        return await asyncio.to_thread(input, prompt)
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.readline()
    if line == "":
        raise EOFError
    return line.rstrip("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive CLI for the AI assistant.")
    parser.add_argument("--plain", action="store_true", help="Disable ANSI styling and spinner.")
    parser.add_argument("--debug", action="store_true", help="Show debug logs.")
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.DEBUG if args.debug else logging.WARNING,
    )

    ui = UI(plain=args.plain)
    _setup_readline()
    try:
        asyncio.run(_chat_loop(ui))
    except RuntimeError as exc:
        ui.line(ui.red(f"Startup failed: {exc}"))


if __name__ == "__main__":
    main()
