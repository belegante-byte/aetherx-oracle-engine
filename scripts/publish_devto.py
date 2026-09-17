#!/usr/bin/env python3
"""Publish marketing/article_devto.md to DEV Community via the Forem API.

Usage:
    python scripts/publish_devto.py --check      # validate the API key only
    python scripts/publish_devto.py --draft      # create as unpublished draft
    python scripts/publish_devto.py              # publish live

Reads DEVTO_API_KEY from config/.env.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "config" / ".env"
ARTICLE = ROOT / "marketing" / "article_devto.md"
API = "https://dev.to/api"
TAGS = ["python", "ai", "webdev", "tutorial"]
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


def load_env(path: pathlib.Path = ENV_FILE) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def request(url: str, *, key: str, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("api-key", key)
    req.add_header("Accept", "application/vnd.forem.api-v1+json")
    req.add_header("User-Agent", USER_AGENT)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            body = json.dumps(json.loads(body))
        except json.JSONDecodeError:
            pass
        return exc.code, {"raw": body}


def split_title(markdown: str) -> tuple[str, str]:
    lines = markdown.splitlines()
    title = ""
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            body_start = i + 1
            break
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1
    return title, "\n".join(lines[body_start:])


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="only validate the API key")
    mode.add_argument("--draft", action="store_true", help="create as an unpublished draft")
    args = parser.parse_args()

    env = load_env()
    key = env.get("DEVTO_API_KEY", "")
    if not key:
        print("ERRO: DEVTO_API_KEY ausente em", ENV_FILE)
        return 1

    status, me = request(f"{API}/users/me", key=key)
    if status != 200:
        print(f"ERRO: chave invalida (http {status}): {me}")
        return 1
    print(f"chave OK -> @{me.get('username')} ({me.get('name')})")

    if args.check:
        return 0

    title, body = split_title(ARTICLE.read_text(encoding="utf-8"))
    if not title:
        print("ERRO: titulo (# H1) nao encontrado em", ARTICLE)
        return 1

    payload = {
        "article": {
            "title": title,
            "body_markdown": body,
            "published": not args.draft,
            "tags": TAGS,
        }
    }
    status, result = request(f"{API}/articles", key=key, method="POST", payload=payload)
    if status not in (200, 201):
        print(f"ERRO ao publicar (http {status}): {result}")
        return 1

    state = "RASCUNHO" if args.draft else "PUBLICADO"
    print(f"{state}: {result.get('url')}")
    print(f"  id={result.get('id')} | title={title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
