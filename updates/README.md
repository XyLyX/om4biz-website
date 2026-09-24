# Publishing to /updates/ and /feed.xml

This section is generated at **Netlify build time**, not by hand and not
by a manual local step. `updates/updates.json` is the single source of
truth — everything else (the hub listing, each entry's page, and the root
`feed.xml`) is regenerated automatically on every deploy.

See `netlify.toml` at the repo root for the exact build command and
publish directory.

## To publish a real update

1. Open `updates/updates.json`.
2. Copy the block from `updates/updates.example.json` into the array and
   fill it in with genuine information — see field notes below.
3. Commit and push `updates/updates.json`. That's it — Netlify runs the
   build (`scripts/build_updates.py` then `scripts/build_public.py`) and
   the new entry appears in the hub, the feed, and gets its own page.

You can still run the build locally to preview before pushing:

```
python3 scripts/build_updates.py && python3 scripts/build_public.py
```

This writes generated pages to `.build/` (gitignored) and assembles the
full publishable site into `public/` (also gitignored) — open
`public/updates/index.html` in a browser to check it before pushing.

## Field notes

- `slug` — lowercase, hyphen-separated, becomes part of the permanent URL
  and the RSS GUID. **Never change a slug after publishing** — that breaks
  the permalink and duplicates the item for anyone subscribed to the feed
  (including NavvyaSignal V2's "From the Navvya Network" section).
- `type` — one of `Announcement`, `Launch`, `Milestone`, `Insight`. Nothing
  else; the build fails on other values.
- `date` — the genuine publication date (`YYYY-MM-DD`), not a placeholder.
  Never backdate or postdate an entry to reorder the feed. An entry dated
  in the future is automatically excluded from every output (hub, feed,
  and its own page) until that date arrives *and* something rebuilds the
  site — Netlify doesn't rebuild on its own just because a date passed, so
  a future-dated entry needs a fresh push (or a scheduled build, if you
  set one up later) on or after its date to actually go live.
- `draft` — optional, boolean, default `false`. Set `true` to stage an
  entry in the repo without publishing it anywhere yet — it's fully
  excluded from the hub, the feed, and gets no page of its own. Flip it
  to `false` (or remove it) when ready to publish.
- `excerpt` — one or two honest sentences. This is what shows in the
  listing card and in the RSS `<description>` — keep it accurate on its
  own, since some readers (including feed consumers) may show only this.
- `image` — optional. Either a site-relative path to a real image file you
  add under `updates/<slug>/`, or leave `""`. Don't reference an image
  that doesn't exist.
- `body_html` — the full article body as plain HTML paragraphs.

## What NOT to publish here

Ordinary website copy edits, design tweaks, or internal changes don't
belong in this feed — only genuinely published articles, product
announcements, venture launches, milestones, or original business
insights. If in doubt, leave it out; this feed is public and syndicated.

## Removing or correcting a published entry

The build doesn't need manual cleanup for removed entries — delete the
block from `updates.json` (or set `"draft": true`) and push; the next
build simply won't include it in `.build/` or `public/`. Nothing stale is
left behind, since `public/` and `.build/` are rebuilt from scratch every
time (see `build_public.py`, which deletes and recreates `public/` on
every run).

## What's committed vs. generated

Committed (source): `updates/updates.json`, `updates/updates.example.json`,
this README, and `scripts/`.

Generated, never committed (`.gitignore`'d): `.build/`, `public/` —
including `updates/index.html`, `updates/<slug>/index.html`, and the root
`feed.xml`. Don't hand-edit anything under `public/` or `.build/`; it's
overwritten on the next build.
