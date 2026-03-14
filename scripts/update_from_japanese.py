#!/usr/bin/env python3
"""
update_from_japanese.py

Fetches pages from the Japanese Tokyo Police Hospital website,
detects content changes, translates to English using Google Translate
(free, no API key required), and updates Hugo Markdown content files.

Usage:
    python scripts/update_from_japanese.py

Requirements:
    pip install -r scripts/requirements.txt
"""

import json
import hashlib
import os
import re
import time
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
PAGE_MAP     = SCRIPT_DIR / "page_map.json"
HASH_FILE    = SCRIPT_DIR / "content_hashes.json"

# ── Settings ───────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT  = 30   # seconds
SLEEP_BETWEEN    = 2    # seconds between requests (be polite)
MAX_CHUNK_LEN    = 4500 # Google Translate free limit per request


# ── Translation helpers ────────────────────────────────────────────────────

def translate_text(text: str, src: str = "ja", tgt: str = "en") -> str:
    """Translate text using Google Translate (free, no API key)."""
    text = text.strip()
    if not text:
        return text

    translator = GoogleTranslator(source=src, target=tgt)

    # Split into chunks to stay within free-tier limits
    chunks = []
    while len(text) > MAX_CHUNK_LEN:
        split_at = text.rfind("\n", 0, MAX_CHUNK_LEN)
        if split_at == -1:
            split_at = MAX_CHUNK_LEN
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    chunks.append(text)

    translated_parts = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        try:
            result = translator.translate(chunk)
            translated_parts.append(result or chunk)
        except Exception as exc:
            print(f"    [warn] Translation failed for chunk: {exc}")
            translated_parts.append(chunk)  # fall back to original
        time.sleep(0.5)

    return "\n".join(translated_parts)


def translate_element(el) -> str:
    """
    Recursively translate a BeautifulSoup element,
    preserving block-level HTML structure as Markdown.
    """
    tag = el.name if el.name else None

    # Plain text node
    if tag is None:
        text = el.string or ""
        return translate_text(text) if text.strip() else text

    # Block elements → convert to Markdown equivalents
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        inner = el.get_text(separator=" ", strip=True)
        translated = translate_text(inner)
        return "\n" + "#" * level + " " + translated + "\n"

    if tag == "p":
        inner = el.get_text(separator=" ", strip=True)
        if not inner:
            return ""
        translated = translate_text(inner)
        return "\n" + translated + "\n"

    if tag in ("ul", "ol"):
        items = []
        for li in el.find_all("li", recursive=False):
            text = li.get_text(separator=" ", strip=True)
            translated = translate_text(text)
            items.append("- " + translated)
        return "\n" + "\n".join(items) + "\n"

    if tag == "table":
        return "\n" + translate_table(el) + "\n"

    if tag in ("div", "section", "article", "main"):
        parts = []
        for child in el.children:
            if hasattr(child, "name"):
                parts.append(translate_element(child))
            else:
                t = str(child).strip()
                if t:
                    parts.append(translate_text(t))
        return "\n".join(parts)

    if tag == "a":
        text = el.get_text(strip=True)
        href = el.get("href", "")
        translated_text = translate_text(text) if text.strip() else text
        return f"[{translated_text}]({href})"

    if tag in ("strong", "b"):
        text = el.get_text(strip=True)
        return "**" + translate_text(text) + "**"

    if tag in ("em", "i"):
        text = el.get_text(strip=True)
        return "*" + translate_text(text) + "*"

    if tag == "br":
        return "\n"

    # Fallback: extract text
    text = el.get_text(separator=" ", strip=True)
    if not text:
        return ""
    return translate_text(text)


def translate_table(table_el) -> str:
    """Convert an HTML table to Markdown table with translated cells."""
    rows = table_el.find_all("tr")
    if not rows:
        return ""

    md_rows = []
    for i, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        translated_cells = []
        for cell in cells:
            text = cell.get_text(separator=" ", strip=True)
            translated_cells.append(translate_text(text).replace("|", "\\|"))
        md_rows.append("| " + " | ".join(translated_cells) + " |")
        if i == 0:
            md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")

    return "\n".join(md_rows)


# ── Page fetching & extraction ─────────────────────────────────────────────

def fetch_page(url: str) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        print(f"  [error] Could not fetch {url}: {exc}")
        return None


def extract_content(soup: BeautifulSoup) -> tuple[str, str]:
    """
    Extract main content and page title from a parsed Japanese hospital page.
    Returns (title_ja, content_html).
    """
    # Try to find the entry content area (habakiri theme)
    content_div = (
        soup.find("div", class_="entry__content")
        or soup.find("div", class_="entry-content")
        or soup.find("article")
        or soup.find("main")
        or soup.find("div", id="contents")
    )

    title_el = soup.find("h1", class_="entry-title") or soup.find("h1")
    title_ja = title_el.get_text(strip=True) if title_el else ""

    if content_div:
        # Remove the h1 from content to avoid duplication (Hugo frontmatter has title)
        for h1 in content_div.find_all("h1", class_="entry-title"):
            h1.decompose()
        return title_ja, str(content_div)

    return title_ja, str(soup.find("body") or soup)


def content_hash(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


# ── Markdown generation ────────────────────────────────────────────────────

def html_to_markdown(html: str) -> str:
    """Convert HTML content to translated Markdown."""
    soup = BeautifulSoup(html, "lxml")

    # Find the actual content container
    content = (
        soup.find("div", class_="entry__content")
        or soup.find("div", class_="entry-content")
        or soup.find("body")
        or soup
    )

    # Remove sidebar, nav, breadcrumb from content if present
    for sel in ["aside", ".sidebar", ".breadcrumb", ".page-header", "nav"]:
        for el in content.select(sel):
            el.decompose()

    parts = []
    for child in content.children:
        if hasattr(child, "name") and child.name:
            translated = translate_element(child)
            if translated and translated.strip():
                parts.append(translated.strip())

    return "\n\n".join(parts)


def build_markdown(title_en: str, description: str, body_md: str) -> str:
    """Build a complete Hugo Markdown file."""
    # Escape any quotes in front matter values
    title_safe = title_en.replace('"', "'")
    desc_safe  = description.replace('"', "'")

    return f"""---
title: "{title_safe}"
description: "{desc_safe}"
---

{body_md}
"""


# ── Main update logic ──────────────────────────────────────────────────────

def load_hashes() -> dict:
    if HASH_FILE.exists():
        with open(HASH_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_hashes(hashes: dict):
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        json.dump(hashes, f, ensure_ascii=False, indent=2)


def load_page_map() -> list:
    with open(PAGE_MAP, encoding="utf-8") as f:
        return json.load(f)


def process_page(entry: dict, hashes: dict) -> bool:
    """
    Fetch, compare, translate, and write one page.
    Returns True if the file was updated.
    """
    ja_url  = entry["ja_url"]
    en_file = PROJECT_ROOT / entry["en_file"]
    en_title = entry.get("en_title", "")
    section  = entry.get("section", "")

    print(f"  Checking: {ja_url}")

    soup = fetch_page(ja_url)
    if soup is None:
        return False

    title_ja, content_html = extract_content(soup)
    h = content_hash(content_html)

    if hashes.get(ja_url) == h:
        print(f"    → No change, skipping.")
        return False

    print(f"    → Content changed, translating...")

    # Translate title
    title_en = translate_text(title_ja) if title_ja else en_title
    if not title_en:
        title_en = en_title

    # Translate body
    body_md = html_to_markdown(content_html)

    # Description: first paragraph
    lines = [l for l in body_md.split("\n") if l.strip() and not l.startswith("#")]
    description = lines[0][:120].rstrip() if lines else en_title

    # Write Markdown file
    en_file.parent.mkdir(parents=True, exist_ok=True)
    markdown = build_markdown(title_en, description, body_md)
    with open(en_file, "w", encoding="utf-8") as f:
        f.write(markdown)

    hashes[ja_url] = h
    print(f"    → Written: {en_file.relative_to(PROJECT_ROOT)}")
    return True


def main():
    print("=" * 60)
    print("Tokyo Police Hospital – English site auto-update")
    print("=" * 60)

    page_map = load_page_map()
    hashes   = load_hashes()

    updated = 0
    failed  = 0

    for entry in page_map:
        try:
            changed = process_page(entry, hashes)
            if changed:
                updated += 1
        except Exception as exc:
            print(f"  [error] Unexpected error for {entry.get('ja_url')}: {exc}")
            failed += 1

        time.sleep(SLEEP_BETWEEN)

    save_hashes(hashes)

    print()
    print(f"Done. Updated: {updated} / Total: {len(page_map)} / Errors: {failed}")

    if updated == 0:
        print("No changes detected – English site is up to date.")
    else:
        print(f"{updated} page(s) updated. Commit and push to deploy.")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
