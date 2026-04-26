# Publishing Pipeline

`publish.py` converts Google Docs into MDSynapse pages. It has two modes:

- **review** — paper reviews from the Reviews Drive folder, written to
  `Reviews/{slug}.html`, with a card injected into `papers-of-note.html`.
- **blog** — free-form blog posts from the Blog Drive folder, written to
  `BlogPosts/{slug}.html`, with a card injected into the `articles-grid` in
  `index.html`.

Both modes share auth, Drive listing, HTML cleaning, and the
`.publish_state.json` ledger that tracks which docs have already been published.

---

## End-to-end pipeline

1. Auth via service account (`n8n/noted-sled-489022-a2-2d59b1c03f2f.json`) — no
   browser flow needed.
2. List Google Docs in the chosen folder; filter out doc IDs already recorded
   in `.publish_state.json`.
3. Export each doc as HTML via the Drive API.
4. **Review mode**: parse the required metadata table → split body at the five
   required H2 sections (`Why This Paper Matters`, `What They Did`, `Key
   Findings`, `What This Means`, `Bottom Line`, plus optional `References`).
   **Blog mode**: take the first H1 as the title; optional italic-paragraph or
   H2 subtitle; everything else is body. An optional metadata table can
   override slug, category, tag class, date, read time, and meta description.
5. Clean Google's exported HTML — strip `style`/`id`/`class`, unwrap `<span>`s,
   resolve `google.com/url?q=…` redirects, preserve images.
6. Process `[CALLOUT] … [/CALLOUT]` and `[QUOTE] … [/QUOTE]` markers into
   site-styled callout / blockquote boxes.
7. Fill the appropriate template (`Reviews/_review-template.html` or
   `BlogPosts/_blog-template.html`) with the rendered content.
8. Write the new HTML file.
9. Inject a card on the listing page (`papers-of-note.html` or `index.html`),
   newest-first, duplicate-safe.
10. Record `{doc_id: {type, slug, published_at}}` in `.publish_state.json`.

---

## One-time setup

1. **Folder IDs** — confirm both are set at the top of `publish.py`:
   - `REVIEW_FOLDER_ID` (from the Drive folder URL)
   - `BLOG_FOLDER_ID`
2. **Service account** — confirm `SERVICE_ACCOUNT_FILE` points to the JSON key
   (already set to `n8n/noted-sled-489022-a2-2d59b1c03f2f.json`). The file is
   `.gitignore`'d; if it's missing locally, regenerate it from Google Cloud
   Console.
3. **Sharing** — share **both** Drive folders with the service-account email
   that appears inside the JSON key (the `client_email` field). Read access is
   enough.

---

## Day-to-day usage

```bash
# Interactive — script asks "review or blog?"
uv run publish.py

# All new blog posts
uv run publish.py --mode blog

# All new reviews
uv run publish.py --mode review

# One specific doc by ID (works in either mode)
uv run publish.py --mode blog --doc-id 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms

# Safe preview before writing anything
uv run publish.py --mode blog --doc-id DOC_ID --dry-run

# Re-publish an already-processed doc (overwrites the HTML)
uv run publish.py --mode review --doc-id DOC_ID --reprocess
```

The Drive doc ID is the long string in the URL after `/d/` and before `/edit`.

---

## Doc structure references

- `Reviews/_review-guide.md` — required metadata table + H2 sections for reviews.
- `BlogPosts/_blog-guide.md` — minimal blog format (just an H1 + body) and the
  optional metadata table for overriding defaults.

---

## State file & migration

State lives in `.publish_state.json` at the repo root. Schema:

```json
{
  "processed": {
    "<google-doc-id>": {
      "type": "review" | "blog",
      "slug": "multimodal-learning-healthcare",
      "published_at": "2026-04-24T12:34:56.789012"
    }
  }
}
```

On first run after upgrade, the script automatically migrates entries from the
old `.review_state.json` (tagging them as `type: "review"`). The legacy file is
left in place; you can delete it once you're confident the migration worked.

---

## What changed from `publish_review.py`

The old `publish_review.py` is now superseded by `publish.py`. The new script
is a strict superset:

- Same review pipeline, same metadata format, same template, same papers-of-note
  card markup — re-running on already-processed reviews is a no-op (state file
  is migrated automatically).
- Adds blog publishing as a second mode with its own template and index-page
  card injection.
- Adds `--mode {review,blog}` flag and an interactive prompt when omitted.

Once you're happy, you can `rm publish_review.py`. (Keeping it around won't
break anything — the two scripts read different state-file paths after migration.)
