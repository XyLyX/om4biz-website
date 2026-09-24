#!/usr/bin/env python3
"""
Assemble public/ — the Netlify publish directory — from approved public
website files plus the generated output in .build/.

Run after build_updates.py (see netlify.toml, which runs both in order).
Rebuilds public/ from scratch every time, so it never carries stale files
from a previous build.

What goes into public/:
  - The 12 existing site pages and shared assets, copied as-is.
  - robots.txt, sitemap.xml, og-image.png.
  - .build/updates/  -> public/updates/   (generated hub + published entries)
  - .build/feed.xml  -> public/feed.xml   (generated feed)

What is explicitly excluded (never copied):
  - scripts/                        (build tooling)
  - updates/README.md               (internal documentation)
  - updates/updates.json            (source data — not a page)
  - updates/updates.example.json    (internal documentation)
  - any draft or future-dated entry (never enters .build/ in the first
    place, so there's nothing to exclude here — see build_updates.py)
  - .git, netlify.toml, .build/ itself
"""
import os
import shutil

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR = os.path.join(SITE_ROOT, ".build")
PUBLIC_DIR = os.path.join(SITE_ROOT, "public")

# Existing site pages (directories) copied as-is.
PAGE_DIRS = [
    "about", "what-we-do", "business-consulting", "business-operations-bpo",
    "customer-experience", "technology-ai", "venture-building", "ventures",
    "leadership", "work-with-us", "contact", "assets",
]
ROOT_FILES = ["index.html", "robots.txt", "sitemap.xml", "og-image.png"]


def main():
    if os.path.isdir(PUBLIC_DIR):
        shutil.rmtree(PUBLIC_DIR)
    os.makedirs(PUBLIC_DIR, exist_ok=True)

    copied = []
    for name in ROOT_FILES:
        src = os.path.join(SITE_ROOT, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(PUBLIC_DIR, name))
            copied.append(name)

    for d in PAGE_DIRS:
        src = os.path.join(SITE_ROOT, d)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(PUBLIC_DIR, d))
            copied.append(d + "/")

    build_updates_dir = os.path.join(BUILD_DIR, "updates")
    if os.path.isdir(build_updates_dir):
        shutil.copytree(build_updates_dir, os.path.join(PUBLIC_DIR, "updates"))
        copied.append("updates/ (generated)")

    build_feed = os.path.join(BUILD_DIR, "feed.xml")
    if os.path.isfile(build_feed):
        shutil.copy2(build_feed, os.path.join(PUBLIC_DIR, "feed.xml"))
        copied.append("feed.xml (generated)")

    print(f"Assembled public/ from {len(copied)} source(s): {', '.join(copied)}")


if __name__ == "__main__":
    main()
