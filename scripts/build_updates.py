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
<script src="/assets/share.js"></script>
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

<section class="page-hero insights-hero">
  <div class="wrap">
    <span class="mono">Insights</span>
    <h1>News, launches and insights from across OM4Biz.</h1>
    <p class="lead">Product announcements, venture launches, milestones and original business insights — published here as they genuinely happen. <a href="/feed.xml" class="rss-link">Subscribe via RSS →</a></p>
  </div>
</section>

<section class="insights-main">
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
    byline = f'<p class="update-byline">By <strong>{escape_html(author)}</strong></p>' if author else ""
    share = share_html(canonical, e["title"])
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

<section class="page-hero insights-hero">
  <div class="wrap">
    <span class="mono update-meta">{format_display_date(e["date"])} · {e["type"]}</span>
    <h1>{escape_html(e['title'])}</h1>
    <p class="lead">{escape_html(e['excerpt'])}</p>
    {byline}
    {share}
  </div>
</section>

<section class="insights-main">
  <div class="wrap" style="max-width:760px;">
    {image_block}
    <div class="update-body">
{e['body_html']}
    </div>
    <div style="margin-top:48px;">{share}</div>
    <p style="margin-top:32px;"><a href="/insights/" class="card-link">← Back to Insights</a></p>
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


def share_html(url, title):
    from urllib.parse import quote
    u, t = quote(url, safe=""), quote(title, safe="")
    return f"""<div class="share-bar" aria-label="Share this article">
      <span class="share-label">Share</span>
      <a class="share-btn" href="https://www.linkedin.com/sharing/share-offsite/?url={u}" target="_blank" rel="noopener" aria-label="Share on LinkedIn"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9.5h4V21H3zM9.5 9.5h3.8v1.6h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21h-4v-5.1c0-1.22-.02-2.78-1.7-2.78-1.7 0-1.95 1.33-1.95 2.7V21h-4z"/></svg></a>
      <a class="share-btn" href="https://twitter.com/intent/tweet?url={u}&amp;text={t}" target="_blank" rel="noopener" aria-label="Share on X (Twitter)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17.75 3h3.07l-6.7 7.66L22 21h-6.17l-4.83-6.32L5.47 21H2.4l7.17-8.2L2 3h6.33l4.37 5.78zm-1.08 16.2h1.7L7.4 4.73H5.58z"/></svg></a>
      <a class="share-btn" href="https://wa.me/?text={t}%20{u}" target="_blank" rel="noopener" aria-label="Share on WhatsApp"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12.04 2a9.9 9.9 0 0 0-8.5 14.98L2 22l5.17-1.5A9.9 9.9 0 1 0 12.04 2zm0 18.1a8.2 8.2 0 0 1-4.2-1.15l-.3-.18-3.07.9.9-2.99-.2-.31a8.2 8.2 0 1 1 6.87 3.73zm4.5-6.14c-.25-.12-1.46-.72-1.69-.8-.22-.08-.39-.12-.55.13-.17.24-.64.8-.78.96-.14.17-.29.19-.53.07-.25-.13-1.05-.39-2-1.23-.73-.66-1.23-1.47-1.38-1.71-.14-.25-.01-.38.11-.5.11-.11.25-.29.37-.43.13-.15.17-.25.25-.42.08-.16.04-.3-.02-.43-.06-.12-.55-1.33-.76-1.82-.2-.48-.4-.41-.55-.42h-.47c-.16 0-.43.06-.65.3-.22.25-.86.84-.86 2.05s.88 2.38 1 2.54c.12.17 1.73 2.64 4.2 3.7.58.26 1.04.41 1.4.52.59.19 1.12.16 1.54.1.47-.07 1.46-.6 1.66-1.17.21-.58.21-1.07.15-1.17-.06-.11-.23-.17-.47-.29z"/></svg></a>
      <button class="share-btn" type="button" data-copy="{url}" aria-label="Copy link"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10.6 13.4a1 1 0 0 1 0-1.4l3.5-3.5a3 3 0 1 1 4.2 4.2l-2 2a1 1 0 1 1-1.4-1.4l2-2a1 1 0 1 0-1.4-1.4l-3.5 3.5a1 1 0 0 1-1.4 0zm2.8-2.8a1 1 0 0 1 0 1.4l-3.5 3.5a3 3 0 1 1-4.2-4.2l2-2a1 1 0 0 1 1.4 1.4l-2 2a1 1 0 1 0 1.4 1.4l3.5-3.5a1 1 0 0 1 1.4 0z"/></svg><span class="share-copied" role="status"></span></button>
    </div>"""


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
