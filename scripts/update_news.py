#!/usr/bin/env python3
"""
update_news.py

Fetches the latest news/announcements from the Japanese Tokyo Police Hospital
website (keisatsubyoin.or.jp/category/all/), translates them to English using
Google Translate (free, no API key), and saves as Hugo Markdown content files
under content/news/.

Each news article becomes an individual English page that can be linked to
directly from the home page news section.

Usage:
    python scripts/update_news.py

Requirements:
    pip install -r scripts/requirements.txt
"""

import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# ── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
NEWS_DIR     = PROJECT_ROOT / "content" / "news"
HASH_FILE    = SCRIPT_DIR / "news_hashes.json"

# ── Settings ─────────────────────────────────────────────────────────────────
NEWS_LIST_URL = "https://www.keisatsubyoin.or.jp/category/all/"
MAX_ARTICLES  = 20          # how many recent articles to keep
MAX_CHUNK_LEN = 4500        # Google Translate free limit
SLEEP_BETWEEN = 2           # seconds between requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Category label map (Japanese → English)
CAT_MAP = {
    "すべて": "All",
    "産婦人科": "Obstetrics & Gynecology",
    "診療科": "Clinical Departments",
    "病院": "Hospital",
    "外来": "Outpatient",
    "入院": "Inpatient",
    "お知らせ": "Announcement",
    "救急": "Emergency",
    "健診": "Health Checkup",
}


# ── Translation helpers ──────────────────────────────────────────────────────

def translate_text(text: str, src: str = "ja", tgt: str = "en") -> str:
    text = text.strip()
    if not text:
        return text
    # Skip translation for already-English text (simple heuristic)
    if all(ord(c) < 128 for c in text):
        return text

    translator = GoogleTranslator(source=src, target=tgt)
    chunks = []
    while len(text) > MAX_CHUNK_LEN:
        split_at = text.rfind("\n", 0, MAX_CHUNK_LEN)
        if split_at == -1:
            split_at = MAX_CHUNK_LEN
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    chunks.append(text)

    parts = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        try:
            result = translator.translate(chunk)
            parts.append(result or chunk)
        except Exception as exc:
            print(f"    [warn] Translation failed: {exc}")
            parts.append(chunk)
        time.sleep(0.3)

    return " ".join(parts)


def translate_cat(cat_ja: str) -> str:
    return CAT_MAP.get(cat_ja.strip(), translate_text(cat_ja))


# ── Fetching ─────────────────────────────────────────────────────────────────

def fetch(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return BeautifulSoup(r.text, "lxml")
    except Exception as exc:
        print(f"  [error] Cannot fetch {url}: {exc}")
        return None


# ── News list parsing ────────────────────────────────────────────────────────

def parse_news_list(soup: BeautifulSoup) -> list[dict]:
    """
    Parse the news list page and return a list of dicts:
      { url, title_ja, date_str, categories_ja }
    """
    articles = []

    # WordPress post items: <article class="post ..."> or <div class="post ...">
    post_els = soup.select("article.post, article[class*='type-post'], div.post")

    if not post_els:
        # Fallback: look for any li/div with a date + link pattern
        post_els = soup.select(".entry-list li, .news-list li, ul.posts li")

    for el in post_els:
        # Title & URL
        title_a = el.select_one("h2 a, h3 a, .entry-title a, a.entry-title")
        if not title_a:
            continue
        url = title_a.get("href", "")
        title_ja = title_a.get_text(strip=True)
        if not url or not title_ja:
            continue

        # Date
        time_el = el.select_one("time[datetime], .entry-date, .posted-on time")
        if time_el:
            date_str = (time_el.get("datetime") or time_el.get_text(strip=True))[:10]
            # Normalize YYYY年MM月DD日 format
            date_str = re.sub(r"(\d{4})年(\d{1,2})月(\d{1,2})日", r"\1-\2-\3", date_str)
        else:
            date_str = datetime.today().strftime("%Y-%m-%d")

        # Categories
        cat_els = el.select(".cat-links a, .category a, .label, .report-categories li")
        cats_ja = [c.get_text(strip=True) for c in cat_els if c.get_text(strip=True)]

        articles.append({
            "url": url,
            "title_ja": title_ja,
            "date_str": date_str[:10],
            "categories_ja": cats_ja,
        })

    return articles[:MAX_ARTICLES]


# ── Article body extraction ──────────────────────────────────────────────────

def extract_article_body(soup: BeautifulSoup) -> str:
    """Extract the main article body as plain text (joined paragraphs)."""
    content = (
        soup.find("div", class_="entry__content")
        or soup.find("div", class_="entry-content")
        or soup.find("article")
        or soup.find("main")
    )
    if not content:
        return ""

    # Remove unwanted sub-elements
    for sel in ["aside", ".sidebar", ".breadcrumb", ".page-header",
                "nav", ".sharedaddy", ".post-navigation", "script", "style"]:
        for el in content.select(sel):
            el.decompose()
    # Remove the h1 title (we get it from the list page)
    for h1 in content.find_all("h1"):
        h1.decompose()

    parts = []
    for el in content.find_all(["p", "h2", "h3", "h4", "ul", "ol", "table"]):
        text = el.get_text(separator=" ", strip=True)
        if text:
            parts.append(text)

    return "\n\n".join(parts)


# ── Slug generation ───────────────────────────────────────────────────────────

def url_to_slug(url: str) -> str:
    """Derive a slug from a WordPress post URL."""
    path = urlparse(url).path.rstrip("/")
    segments = [s for s in path.split("/") if s]
    # WP URLs are often /YYYY/MM/DD/slug or /slug/
    for seg in reversed(segments):
        if not re.match(r"^\d+$", seg):  # skip pure-number segments
            return re.sub(r"[^\w-]", "-", seg)[:60]
    return hashlib.md5(url.encode()).hexdigest()[:12]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ── Markdown writing ─────────────────────────────────────────────────────────

def write_article(article: dict) -> None:
    date = article["date_str"]
    slug = article["slug"]
    filename = NEWS_DIR / f"{date}-{slug}.md"

    cats_en = article["categories_en"]
    cats_yaml = ", ".join(f'"{c}"' for c in cats_en) if cats_en else '"All"'

    title_safe = article["title_en"].replace('"', "'")
    desc_safe  = article["body_en"][:120].replace('"', "'").replace("\n", " ")

    md = f"""---
title: "{title_safe}"
date: {date}
categories: [{cats_yaml}]
description: "{desc_safe}"
---

{article["body_en"]}
"""
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"    → Written: content/news/{filename.name}")


# ── Hashes ───────────────────────────────────────────────────────────────────

def load_hashes() -> dict:
    if HASH_FILE.exists():
        with open(HASH_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_hashes(hashes: dict) -> None:
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        json.dump(hashes, f, ensure_ascii=False, indent=2)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Tokyo Police Hospital – News auto-update")
    print("=" * 60)

    hashes = load_hashes()
    updated = 0
    failed = 0

    # Step 1: Fetch the news list
    print(f"\nFetching news list: {NEWS_LIST_URL}")
    list_soup = fetch(NEWS_LIST_URL)
    if list_soup is None:
        print("[error] Could not fetch news list. Aborting.")
        sys.exit(1)

    articles = parse_news_list(list_soup)
    if not articles:
        print("[warn] No articles found on news list page.")
        sys.exit(0)

    print(f"Found {len(articles)} articles.\n")

    # Step 2: Process each article
    for art in articles:
        url       = art["url"]
        title_ja  = art["title_ja"]
        date_str  = art["date_str"]
        cats_ja   = art["categories_ja"]
        slug      = url_to_slug(url)

        print(f"  [{date_str}] {title_ja[:50]}")

        try:
            # Fetch individual article
            art_soup = fetch(url)
            time.sleep(SLEEP_BETWEEN)

            body_ja = ""
            if art_soup:
                body_ja = extract_article_body(art_soup)

            # Hash check
            raw = title_ja + body_ja
            h = content_hash(raw)
            if hashes.get(url) == h:
                print("    → No change, skipping.")
                continue

            # Translate
            print("    → Translating...")
            title_en = translate_text(title_ja)
            body_en  = translate_text(body_ja) if body_ja else title_en
            cats_en  = [translate_cat(c) for c in cats_ja] if cats_ja else ["Announcement"]

            article_data = {
                "slug":         slug,
                "date_str":     date_str,
                "title_en":     title_en,
                "body_en":      body_en,
                "categories_en": cats_en,
            }

            write_article(article_data)
            hashes[url] = h
            updated += 1

        except Exception as exc:
            print(f"    [error] {exc}")
            failed += 1

        time.sleep(SLEEP_BETWEEN)

    save_hashes(hashes)

    print()
    print(f"Done. Updated: {updated} / Total: {len(articles)} / Errors: {failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
