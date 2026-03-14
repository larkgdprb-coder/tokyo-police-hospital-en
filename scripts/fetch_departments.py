#!/usr/bin/env python3
"""
fetch_departments.py

Fetches each department page from the Japanese hospital website,
translates to English, and writes Hugo Markdown files.
"""

import time
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

BASE_URL = "https://www.keisatsubyoin.or.jp"
PROJECT_ROOT = Path(__file__).parent.parent
MAX_CHUNK = 4500

DEPARTMENTS = [
    ("General Internal Medicine",        "/shinryoka/naika/",       "internal-medicine"),
    ("Neurology",                         "/shinryoka/nou-naika/",   "neurology"),
    ("Respiratory Medicine",              "/shinryoka/kokyuki/",     "respiratory-medicine"),
    ("Gastroenterology",                  "/shinryoka/syoukaki/",    "gastroenterology"),
    ("Cardiology",                        "/shinryoka/junkanki/",    "cardiology"),
    ("Nephrology & Metabolism",           "/shinryoka/jintaisya/",   "nephrology"),
    ("Hematology",                        "/shinryoka/ketsueki/",    "hematology"),
    ("Rheumatology & Collagen Disease",   "/shinryoka/riumati/",     "rheumatology"),
    ("Psychiatry",                        "/shinryoka/sinkei/",      "psychiatry"),
    ("Pediatrics",                        "/shinryoka/syouni/",      "pediatrics"),
    ("Surgery (General & Gastrointestinal)", "/shinryoka/geka/",     "surgery"),
    ("Orthopedic Surgery",                "/shinryoka/seikei/",      "orthopedics"),
    ("Plastic & Aesthetic Surgery",       "/shinryoka/keisei/",      "plastic-surgery"),
    ("Neurosurgery",                      "/shinryoka/nousinkei/",   "neurosurgery"),
    ("Cerebrovascular Intervention",      "/shinryoka/noukekkan/",   "cerebrovascular-intervention"),
    ("Dermatology",                       "/shinryoka/hihu/",        "dermatology"),
    ("Urology",                           "/shinryoka/hinyou/",      "urology"),
    ("Obstetrics & Gynecology",           "/shinryoka/sanhu/",       "obstetrics-gynecology"),
    ("Ophthalmology",                     "/shinryoka/ganka/",       "ophthalmology"),
    ("Otolaryngology (ENT)",              "/shinryoka/jibi/",        "otolaryngology"),
    ("Emergency & Critical Care Medicine","/shinryoka/kyukyu/",      "emergency-medicine"),
    ("Rehabilitation Medicine",           "/shinryoka/rihabiri/",    "rehabilitation"),
    ("Radiology",                         "/shinryoka/housyasen/",   "radiology"),
    ("Anesthesiology",                    "/shinryoka/masui/",       "anesthesiology"),
    ("Pathology",                         "/shinryoka/byouri/",      "pathology"),
]


def translate_text(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    translator = GoogleTranslator(source="ja", target="en")
    chunks = []
    while len(text) > MAX_CHUNK:
        split_at = text.rfind("\n", 0, MAX_CHUNK)
        if split_at == -1:
            split_at = MAX_CHUNK
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
        except Exception as e:
            print(f"    [warn] translation error: {e}")
            parts.append(chunk)
        time.sleep(0.5)
    return "\n".join(parts)


def element_to_markdown(el) -> str:
    tag = el.name if el.name else None
    if tag is None:
        text = str(el).strip()
        return translate_text(text) if text else ""

    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        inner = el.get_text(separator=" ", strip=True)
        if not inner:
            return ""
        translated = translate_text(inner)
        return "\n" + "#" * level + " " + translated + "\n"

    if tag == "p":
        inner = el.get_text(separator=" ", strip=True)
        if not inner:
            return ""
        return "\n" + translate_text(inner) + "\n"

    if tag in ("ul", "ol"):
        items = []
        for li in el.find_all("li", recursive=False):
            text = li.get_text(separator=" ", strip=True)
            if text:
                items.append("- " + translate_text(text))
        return ("\n" + "\n".join(items) + "\n") if items else ""

    if tag == "table":
        return "\n" + translate_table(el) + "\n"

    if tag in ("div", "section", "article"):
        parts = []
        for child in el.children:
            if hasattr(child, "name") and child.name:
                result = element_to_markdown(child)
                if result and result.strip():
                    parts.append(result.strip())
            else:
                t = str(child).strip()
                if t:
                    translated = translate_text(t)
                    if translated:
                        parts.append(translated)
        return "\n\n".join(parts) if parts else ""

    if tag in ("strong", "b"):
        text = el.get_text(strip=True)
        return "**" + translate_text(text) + "**" if text else ""

    if tag in ("em", "i"):
        text = el.get_text(strip=True)
        return "*" + translate_text(text) + "*" if text else ""

    if tag == "br":
        return "\n"

    # fallback
    text = el.get_text(separator=" ", strip=True)
    return translate_text(text) if text else ""


def translate_table(table_el) -> str:
    rows = table_el.find_all("tr")
    if not rows:
        return ""
    md_rows = []
    for i, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        translated_cells = [
            translate_text(c.get_text(separator=" ", strip=True)).replace("|", "\\|")
            for c in cells
        ]
        md_rows.append("| " + " | ".join(translated_cells) + " |")
        if i == 0:
            md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n".join(md_rows)


def fetch_and_translate(en_title: str, ja_path: str) -> tuple[str, str]:
    """Returns (translated_title, markdown_body)"""
    url = BASE_URL + ja_path
    print(f"  Fetching: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
    except Exception as e:
        print(f"  [error] {e}")
        return en_title, f"*Content not available. Please visit [{en_title}]({url})*"

    soup = BeautifulSoup(resp.text, "lxml")

    # Extract main content
    content = (
        soup.find("div", class_="entry__content")
        or soup.find("div", class_="entry-content")
        or soup.find("article")
        or soup.find("main")
    )

    if not content:
        print("  [warn] No content area found")
        return en_title, f"*Content not available.*"

    # Remove nav, sidebar, breadcrumb, scripts, styles
    for sel in ["aside", "nav", ".breadcrumb", ".breadcrumbs", ".sidebar",
                 "script", "style", ".page-header", ".entry-title"]:
        for el in content.select(sel):
            el.decompose()

    # Also remove h1 title (avoid duplication with frontmatter)
    for h1 in content.find_all("h1"):
        h1.decompose()

    # Extract page title from soup for translation
    title_el = soup.find("h1", class_="entry-title") or soup.find("h1")
    title_ja = title_el.get_text(strip=True) if title_el else ""

    # Translate title (strip the English part if combined like "泌尿器科Urology")
    title_en = en_title
    if title_ja:
        # Remove any ASCII portion before translating
        ja_only = re.sub(r'[A-Za-z\s/&()]+$', '', title_ja).strip()
        if ja_only:
            try:
                title_en = translate_text(ja_only) or en_title
            except Exception:
                title_en = en_title

    # Build markdown from content
    parts = []
    for child in content.children:
        if hasattr(child, "name") and child.name:
            result = element_to_markdown(child)
            if result and result.strip():
                parts.append(result.strip())

    body = "\n\n".join(parts)
    return title_en, body


def write_md(slug: str, title: str, body: str):
    out_path = PROJECT_ROOT / "content" / "departments" / f"{slug}.md"

    # Get first non-heading line for description
    lines = [l for l in body.split("\n") if l.strip() and not l.startswith("#")]
    description = lines[0][:120].rstrip() if lines else title
    # Remove markdown special chars from description
    description = description.replace('"', "'").replace('*', '').replace('_', '')

    title_safe = title.replace('"', "'")
    content = f"""---
title: "{title_safe}"
description: "{description}"
---

{body}
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Written: content/departments/{slug}.md")


def main():
    print("=" * 60)
    print("Fetching & translating department pages")
    print("=" * 60)

    for en_title, ja_path, slug in DEPARTMENTS:
        print(f"\n[{slug}]")
        title, body = fetch_and_translate(en_title, ja_path)
        write_md(slug, title, body)
        time.sleep(2)

    print("\nDone.")


if __name__ == "__main__":
    main()
