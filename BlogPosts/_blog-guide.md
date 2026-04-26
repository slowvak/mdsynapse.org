# Blog Post — Google Doc Structure Guide

Free-form Google Docs are converted into NeoSynapse blog posts by `publish.py
--mode blog`. Unlike paper reviews, **no metadata table is required** — the script
infers what it needs from the document. Add a metadata table only when you want
to override the defaults.

---

## Minimum required structure

1. **Title** — the very first content in the doc, styled as Heading 1 (`Format
   → Paragraph styles → Heading 1`). The script reads its plain text and uses it
   as both the page `<h1>` and the source for the slug.
2. **Body** — anything after the title. Paragraphs, lists, images, links,
   blockquotes, H2/H3 subheadings — all preserved.

Everything else has reasonable defaults.

---

## Inferred / defaulted fields

| Field | How it is derived | Override key |
|---|---|---|
| Slug | `slugify(Title)` — lowercase, hyphenated, ASCII-safe | `Slug` |
| Subtitle | First paragraph if it is fully italic, OR an H2 immediately under the title; otherwise omitted | `Subtitle` |
| Date | Drive's `modifiedTime` for the doc; today if missing | `Date` |
| Read Time | `round(word_count / 200)`, minimum 1 | `Read Time` |
| Category | `AI` | `Category` |
| Tag Class | `tag-ai` | `Tag Class` |
| Meta Description | Lead paragraph (first non-empty `<p>`), trimmed to 160 chars | `Meta Description` |
| Excerpt (index card) | Same as Meta Description, trimmed to 240 chars | `Meta Description` |

---

## Optional metadata table

To override any default, put a 2-column key/value table as the **very first
content** in the doc (above the H1). Example with the most useful overrides:

| Key | Value |
|---|---|
| `Title` | Beyond the Screen: The Biological AI Revolution |
| `Subtitle` | Why the next explosion in intelligence won't happen on your phone |
| `Slug` | bio-ai |
| `Category` | Bio AI |
| `Tag Class` | tag-ai |
| `Date` | February 28, 2026 |
| `Read Time` | 10 |
| `Meta Description` | A 150-char SEO blurb shown on the index card and in `<meta>` tags. |

Valid `Tag Class` values: `tag-ai`, `tag-clinical`, `tag-ethics`, `tag-future`.
Anything else falls back to `tag-ai` with a warning.

---

## Inline content tips

- **Lead paragraph** — the first non-empty paragraph after the title becomes the
  styled lead (larger text). Write it as a strong opener.
- **Headings** — use H2 for major sections, H3 for sub-sections. They render
  with the same styling as the hand-written posts in `BlogPosts/`.
- **Images** — uploaded inline images come through as `<img>` tags. The script
  preserves `src`, `alt`, `width`, `height`. If you need a caption, put the
  caption text in italics on the line directly under the image.
- **Links** — Google's redirect-wrapped URLs (`google.com/url?q=...`) are
  unwrapped automatically and styled in the site's teal accent.
- **Callouts** — wrap a paragraph in `[CALLOUT]` / `[/CALLOUT]` (each on its own
  line) to render the dark callout box used in the site's articles. Wrap with
  `[QUOTE]` / `[/QUOTE]` for a styled pull-quote.

---

## What gets updated when a blog post publishes

- `BlogPosts/{slug}.html` — the new post, modeled on `BlogPosts/_blog-template.html`.
- `index.html` — a new card is inserted as the **first** entry in the
  `<div class="articles-grid">` block (newest first).
- `.publish_state.json` — records `{doc_id: {type: "blog", slug, published_at}}`
  so the same doc isn't reprocessed on the next run.

---

## Naming convention

Output file: `BlogPosts/{slug}.html`. Live URL: `https://mdsynapse.org/BlogPosts/{slug}.html`.

The slug must be unique across BlogPosts/. If you re-publish (with `--reprocess`),
the existing file is overwritten and the index card is left as-is (duplicate-safe).
