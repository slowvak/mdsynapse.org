# Paper Review — Google Doc Structure Guide

This doc defines the required structure for Google Docs that the automation
script will convert into review HTML pages.

---

## Google Doc format

The script recognizes the following **exact H2 heading names**. All other text
under a heading is extracted verbatim and injected into the template.

### Required top-of-doc metadata table

Put this as the very first content — a Google Docs table with two columns
(key / value). The script reads this before any body text.

| Field | Example value | Notes |
|---|---|---|
| `Review Title` | Unpacking Multimodal AI in Healthcare | The h1 shown on the page. Can differ from the paper title. |
| `Subtitle` | When does fusing EHR and X-rays actually help? | One sentence, no period. Appears under the title in the header. |
| `Paper Title` | When Does Multimodal Learning Help in Healthcare? | Full title of the paper being reviewed. |
| `Authors` | Kejing Yin, Haizhou Xu, et al. | Truncate long author lists with "et al." |
| `Venue` | arXiv | Journal name, conference, or "arXiv". |
| `Year` | 2025 | Four-digit year of the paper. |
| `Paper URL` | https://arxiv.org/abs/2602.23614 | Direct link to the paper. |
| `Category` | Multimodal AI | Short label for the category badge. |
| `Tag Class` | tag-ai | CSS class: tag-ai, tag-clinical, tag-ethics, or tag-future. |
| `Date` | April 15, 2026 | Publication date for the review (not the paper). |
| `Read Time` | 12 | Estimated read time in minutes (integer). |
| `Slug` | multimodal-learning-healthcare | URL-safe filename, no .html extension. |
| `Meta Description` | A review of CareBench… | 150 chars max. Used for SEO meta tags. |
| `Tags` | Multimodal AI, EHR, Fairness | Comma-separated list of article tags shown in footer. |

---

## Required H2 sections (exact heading text)

### `Why This Paper Matters`

- First paragraph becomes the styled lead (larger text, teal left border).
- Remaining paragraphs render as normal body text.
- Typical length: 1–3 paragraphs.

### `What They Did`

- Describe the study design, dataset, and methods.
- Use H3 subheadings freely — they render as styled `<h3>` elements.
- Typical length: 2–4 paragraphs with optional sub-sections.

### `Key Findings`

- Each H3 under this section becomes a finding subsection.
- **Optional callout syntax**: start a paragraph with `[CALLOUT]` on its own line
  followed by the callout text, then `[/CALLOUT]`. The script wraps that content
  in the dark `.article-callout` box. Example:

  ```
  ### Finding 1: Fusion helps for modality-distributed diseases

  [CALLOUT]
  Multimodal gains were concentrated in diseases like CHF and COPD
  that require both structural (CXR) and longitudinal (EHR) signals.
  [/CALLOUT]

  Regular paragraph text continues here...
  ```

- **Optional pull-quote syntax**: wrap a sentence in `[QUOTE]...[/QUOTE]` to
  render it as a styled blockquote.

### `What This Means`

- Clinical and research implications.
- Plain paragraphs; H3 subheadings optional.
- Typical length: 2–3 paragraphs.

### `Bottom Line`

- A concise TL;DR of the review — 2–4 sentences.
- Rendered as a prominent dark callout box at the end of the article.
- **Write it like an attending's verbal summary to a resident**: direct, confident,
  clinically grounded.

---

## Optional H2 section

### `References`

- Numbered list. Each item renders as a standard list element.
- Omit this section entirely if not needed.

---

## papers-of-note.html card

When the script publishes a new review, it inserts an `<article>` card into the
`<!-- Paper Cards -->` grid in `papers-of-note.html`. The card uses:

- `Review Title` → `<h3>` title
- `Authors` → italic line
- First sentence of `Why This Paper Matters` → summary paragraph
- `Category` + `"Review Available"` → tag badges
- `Slug` → href for "Read Full Review →"
- `Paper URL` → href for "View Paper →"

The card is always inserted **before** the first existing card (newest first).

---

## Naming convention

Output file: `Reviews/{{SLUG}}.html`

The slug must be unique and match exactly what is in the metadata table.
