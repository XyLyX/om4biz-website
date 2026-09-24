#!/usr/bin/env python3
"""
Build /updates/ pages and /feed.xml from updates/updates.json.

This runs automatically as part of the Netlify build (see netlify.toml) —
it is not a manual step. It reads the single source of truth,
updates/updates.json, and writes generated output to .build/ (gitignored
staging area, never committed). scripts/build_public.py then assembles the
final public/ publish directory from .build/ plus the existing static pages.

Usage:
    python3 scripts/build_updates.py

Entry schema (updates/updates.json — array of objects):
    slug        string, URL-safe, permanent once published (becomes the GUID)
    title       string
    type        one of: Announcement | Launch | Milestone | Insight
    date        ISO date "YYYY-MM-DD", the genuine publication date
    excerpt     1-2 sentences, plain text (used in listing + RSS description)
    image       optional, site-relative path e.g. "/updates/<slug>/cover.jpg"
                (must be a real file you've added — leave "" if none)
    body_html   the full article body as HTML (paragraphs, etc.)
    draft       optional, boolean, default false. true = never rendered into
                any output (hub, feed, or its own page) until set back to
                false. Use this to stage an entry ahead of time.

An entry is only published to the site once BOTH are true: draft is not
true, AND date is today or earlier (UTC). A future date is treated the
same as a draft — silently excluded from every output until that date
arrives and the site is rebuilt again (Netlify only rebuilds on a new
push or a manual/scheduled trigger — a future-dated entry does not appear
automatically the moment its date passes unless something rebuilds it).

See updates/updates.example.json for a template block.
"""
import json
import os
import re
import shutil
from datetime import datetime, timezone, date
from email.utils import format_datetime

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = "https://www.om4biz.com"
DATA_PATH = os.path.join(SITE_ROOT, "updates", "updates.json")
BUILD_DIR = os.path.join(SITE_ROOT, ".build")
VALID_TYPES = {"Announcement", "Launch", "Milestone", "Insight"}

NAV = """<header class="nav">
  <div class="nav-inner">
    <a class="nav-brand" href="/">OM4BIZ GLOBAL SERVICES</a>
    <ul class="nav-links">
      <li><a href="/about/">About</a></li>
      <li><a href="/what-we-do/">What We Do</a></li>
      <li><a href="/ventures/">Ventures</a></li>
      <li><a href="/insights/"{updates_active}>Insights</a></li>
      <li><a href="/leadership/">Leadership</a></li>
      <li><a href="/work-with-us/">Work With Us</a></li>
      <li><a href="/contact/" class="nav-cta">Contact</a></li>
    </ul>
  </div>
</header>"""

FOOTER = """<footer>
  <div class="wrap">
    <div class="footer-grid">
      <div>
        <div class="footer-brand">OM4BIZ</div>
        <p style="max-width:320px;font-size:0.9rem;opacity:0.7;">Build. Operate. Scale. — a Dubai-based business operating and venture group.</p>
      </div>
      <div>
        <h4>Company</h4>
        <ul>
          <li><a href="/about/">About</a></li>
          <li><a href="/what-we-do/">What We Do</a></li>
          <li><a href="/insights/">Insights</a></li>
          <li><a href="/leadership/">Leadership</a></li>
          <li><a href="/contact/">Contact</a></li>
        </ul>
      </div>
      <div>
        <h4>Ventures</h4>
        <ul>
          <li><a href="https://zenhomesglobal.com" target="_blank" rel="noopener">ZenHomes</a></li>
          <li><a href="https://designcode.ae" target="_blank" rel="noopener">Design Code Studio</a></li>
          <li><a href="https://d6kitchens.com" target="_blank" rel="noopener">D6 Kitchens</a></li>
          <li><a href="https://navvyasignal.com" target="_blank" rel="noopener">NavvyaSignal</a></li>
          <li><a href="https://thewasam.com" target="_blank" rel="noopener">The Wasam</a></li>
          <li><a href="https://www.filsonly.com" target="_blank" rel="noopener">FilsOnly</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <span>© 2006–2026 OM4Biz Global Services. All rights reserved.</span>
      <span>hello@om4biz.com · www.om4biz.com</span>
    </div>
  </div>
</footer>

<script src="/assets/reveal.js"></script>
</body>
</html>
"""


def load_entries():
    """Validate every entry (published or not) and return only the
    published subset: draft is not true, and date <= today (UTC)."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)
    seen = set()
    today = datetime.now(timezone.utc).date()
    published = []
    for e in entries:
        missing = [k for k in ("slug", "title", "type", "date", "excerpt", "body_html") if not e.get(k)]
        if missing:
            raise ValueError(f"Entry {e.get('slug', '?')} missing required field(s): {missing}")
        if e["type"] not in VALID_TYPES:
            raise ValueError(f"Entry {e['slug']} has invalid type {e['type']!r}; must be one of {VALID_TYPES}")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", e["slug"]):
            raise ValueError(f"Slug {e['slug']!r} must be lowercase, hyphen-separated, URL-safe")
        if e["slug"] in seen:
            raise ValueError(f"Duplicate slug: {e['slug']}")
        seen.add(e["slug"])
        entry_date = datetime.strptime(e["date"], "%Y-%m-%d").date()  # validates format
        e.setdefault("image", "")
        is_draft = bool(e.get("draft", False))
        is_future = entry_date > today
        e["_excluded_reason"] = "draft" if is_draft else ("future-dated" if is_future else None)
        if e["_excluded_reason"] is None:
            published.append(e)
    published.sort(key=lambda e: e["date"], reverse=True)
    return published


def entry_url(e):
    return f"{BASE_URL}/insights/{e['slug']}/"


def nav_html(active_updates=True):
    return NAV.format(updates_active=' class="active"' if active_updates else "")


def render_hub(entries):
    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Insights | OM4Biz</title>
<meta name="description" content="Product announcements, launches, milestones and original business insights from OM4Biz Global Services and its portfolio.">
<link rel="canonical" href="{BASE_URL}/insights/">
<link rel="alternate" type="application/rss+xml" title="OM4Biz Insights" href="{BASE_URL}/feed.xml">
<meta property="og:title" content="Insights | OM4Biz">
<meta property="og:description" content="Product announcements, launches, milestones and original business insights from OM4Biz Global Services and its portfolio.">
<meta property="og:image" content="{BASE_URL}/og-image.png">
<meta property="og:type" content="website">
<meta property="og:url" content="{BASE_URL}/insights/">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"Home","item":"{BASE_URL}/"}},{{"@type":"ListItem","position":2,"name":"Insights","item":"{BASE_URL}/insights/"}}]}}
</script>
</head>
<body>

{nav_html()}

<nav class="breadcrumb"><div class="wrap"><a href="/">Home</a> / Insights</div></nav>

<section class="page-hero">
  <div class="wrap">
    <span class="mono">Insights</span>
    <h1>News, launches and insights from across OM4Biz.</h1>
    <p class="lead">Product announcements, venture launches, milestones and original business insights — published here as they genuinely happen. <a href="/feed.xml" class="rss-link">Subscribe via RSS →</a></p>
  </div>
</section>

<section>
  <div class="wrap">
"""
    if not entries:
        body = """    <div class="empty-state reveal">
      <p>Nothing published here yet. This page and its <a href="/feed.xml">RSS feed</a> will fill in as OM4Biz has genuine announcements, launches, milestones or insights to share — check back, or subscribe.</p>
    </div>
"""
    else:
        cards = []
        for e in entries:
            img = f'<div class="update-mark" style="background-image:url(\'{e["image"]}\');"></div>' if e["image"] else '<div class="update-mark"></div>'
            cards.append(f"""    <div class="update-card reveal">
      {img}
      <div>
        <span class="mono update-meta">{format_display_date(e["date"])} · {e["type"]}</span>
        <h3><a href="/insights/{e['slug']}/">{escape_html(e['title'])}</a></h3>
        <p>{escape_html(e['excerpt'])}</p>
        <a class="card-link" href="/insights/{e['slug']}/">Read more →</a>
      </div>
    </div>""")
        body = "    <div class=\"update-list\">\n" + "\n".join(cards) + "\n    </div>\n"

    tail = """  </div>
</section>

<section id="contact-section">
  <div class="wrap">
    <div class="section-head reveal">
      <span class="mono">Get in touch</span>
      <h2>Have something worth covering?</h2>
    </div>
    <div class="cta-row reveal">
      <a href="/contact/" class="btn btn-primary" style="background:var(--gold);color:var(--navy);">Start a Conversation</a>
    </div>
  </div>
</section>

""" + FOOTER
    return head + body + tail


def render_entry(e):
    canonical = entry_url(e)
    published_rfc = format_datetime(datetime.strptime(e["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc))
    og_image = e["image"] if e["image"] else f"{BASE_URL}/og-image.png"
    og_image_full = og_image if og_image.startswith("http") else f"{BASE_URL}{og_image}"
    author = e.get("author", "")
    author_role = e.get("author_role", "")
    author_ld = f',"author":{{"@type":"Person","name":{json.dumps(author)},"url":"{BASE_URL}/leadership/"}}' if author else ""
    byline = f'<p class="update-byline">By <strong>{escape_html(author)}</strong>{", " + escape_html(author_role) if author_role else ""}</p>' if author else ""
    image_block = f'<img src="{e["image"]}" alt="{escape_html(e["title"])}" style="width:100%;border-radius:2px;margin-bottom:32px;">' if e["image"] else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape_html(e['title'])} | OM4Biz Insights</title>
<meta name="description" content="{escape_html(e['excerpt'])}">
<link rel="canonical" href="{canonical}">
<link rel="alternate" type="application/rss+xml" title="OM4Biz Insights" href="{BASE_URL}/feed.xml">
<meta property="og:title" content="{escape_html(e['title'])}">
<meta property="og:description" content="{escape_html(e['excerpt'])}">
<meta property="og:image" content="{og_image_full}">
<meta property="og:type" content="article">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Article","headline":{json.dumps(e['title'])},"datePublished":"{e['date']}","description":{json.dumps(e['excerpt'])},"url":"{canonical}","publisher":{{"@type":"Organization","name":"OM4Biz Global Services"}}{author_ld}}}
</script>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"Home","item":"{BASE_URL}/"}},{{"@type":"ListItem","position":2,"name":"Insights","item":"{BASE_URL}/insights/"}},{{"@type":"ListItem","position":3,"name":{json.dumps(e['title'])},"item":"{canonical}"}}]}}
</script>
</head>
<body>

{nav_html()}

<nav class="breadcrumb"><div class="wrap"><a href="/">Home</a> / <a href="/insights/">Insights</a> / {escape_html(e['title'])}</div></nav>

<section class="page-hero">
  <div class="wrap">
    <span class="mono update-meta">{format_display_date(e["date"])} · {e["type"]}</span>
    <h1>{escape_html(e['title'])}</h1>
    <p class="lead">{escape_html(e['excerpt'])}</p>
    {byline}
  </div>
</section>

<section>
  <div class="wrap" style="max-width:760px;">
    {image_block}
    <div class="update-body reveal">
{e['body_html']}
    </div>
    <p style="margin-top:56px;"><a href="/insights/" class="card-link">← Back to Insights</a></p>
  </div>
</section>

<section id="contact-section">
  <div class="wrap">
    <div class="section-head reveal">
      <span class="mono">Get in touch</span>
      <h2>Have something worth covering?</h2>
    </div>
    <div class="cta-row reveal">
      <a href="/contact/" class="btn btn-primary" style="background:var(--gold);color:var(--navy);">Start a Conversation</a>
    </div>
  </div>
</section>

{FOOTER}"""


def render_feed(entries):
    now_rfc = format_datetime(datetime.now(timezone.utc))
    items = []
    for e in entries:
        pub_rfc = format_datetime(datetime.strptime(e["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc))
        url = entry_url(e)
        item = [
            "    <item>",
            f"      <title>{escape_xml(e['title'])}</title>",
            f"      <link>{url}</link>",
            f'      <guid isPermaLink="true">{url}</guid>',
            f"      <pubDate>{pub_rfc}</pubDate>",
            f"      <category>{escape_xml(e['type'])}</category>",
            f"      <description>{escape_xml(e['excerpt'])}</description>",
        ]
        if e["image"]:
            img_url = e["image"] if e["image"].startswith("http") else f"{BASE_URL}{e['image']}"
            item.append(f'      <media:content url="{img_url}" medium="image" />')
        item.append("    </item>")
        items.append("\n".join(item))

    items_xml = "\n".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>OM4Biz Insights</title>
    <link>{BASE_URL}/insights/</link>
    <atom:link href="{BASE_URL}/feed.xml" rel="self" type="application/rss+xml" />
    <description>Product announcements, launches, milestones and original business insights from OM4Biz Global Services and its portfolio.</description>
    <language>en</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
{items_xml}
  </channel>
</rss>
"""


def format_display_date(iso_date):
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%-d %B %Y")


def escape_html(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def escape_xml(s):
    return escape_html(s)


def count_excluded():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    today = datetime.now(timezone.utc).date()
    drafts = sum(1 for e in raw if e.get("draft", False))
    future = sum(1 for e in raw if not e.get("draft", False)
                 and datetime.strptime(e["date"], "%Y-%m-%d").date() > today)
    return drafts, future


def main():
    entries = load_entries()
    drafts, future = count_excluded()

    if os.path.isdir(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    build_updates_dir = os.path.join(BUILD_DIR, "insights")
    os.makedirs(build_updates_dir, exist_ok=True)

    with open(os.path.join(build_updates_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_hub(entries))

    for e in entries:
        entry_dir = os.path.join(build_updates_dir, e["slug"])
        os.makedirs(entry_dir, exist_ok=True)
        with open(os.path.join(entry_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(render_entry(e))

    with open(os.path.join(BUILD_DIR, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(render_feed(entries))

    print(f"Built {len(entries)} published update(s) into .build/ "
          f"(excluded: {drafts} draft, {future} future-dated)")


if __name__ == "__main__":
    main()
