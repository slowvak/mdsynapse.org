#!/usr/bin/env python3
# /// script
# dependencies = [
#   "google-api-python-client>=2.100",
#   "google-auth>=2.23",
#   "beautifulsoup4>=4.12",
#   "python-dateutil>=2.8",
# ]
# ///
"""
publish.py — Convert Google Docs into NeoSynapse HTML pages.

Two modes:
  review  — paper reviews from the Reviews Drive folder, written to Reviews/{slug}.html,
            card injected into papers-of-note.html.
  blog    — free-form blog posts from the Blog Drive folder, written to BlogPosts/{slug}.html,
            card injected into the articles grid in index.html.

Workflow (both modes):
  1. Auth via service-account JSON
  2. List Google Docs in the configured folder, skip ones already processed
  3. Export each doc as HTML via Drive API
  4. Parse + clean the export, fill the appropriate template
  5. Write the new HTML, inject a card on the index/listing page
  6. Record the doc ID in .publish_state.json so it won't be reprocessed

Usage:
  uv run publish.py                                  # interactive: asks review or blog
  uv run publish.py --mode review                    # all new reviews
  uv run publish.py --mode blog                      # all new blog posts
  uv run publish.py --mode blog --doc-id DOC_ID      # publish one specific doc
  uv run publish.py --mode blog --doc-id ID --dry-run
  uv run publish.py --mode review --reprocess --doc-id ID

Setup (one-time):
  1. Set REVIEW_FOLDER_ID and BLOG_FOLDER_ID below
  2. Confirm SERVICE_ACCOUNT_FILE points to your key JSON
  3. Share both Drive folders with the service-account email

Doc formats: see Reviews/_review-guide.md and BlogPosts/_blog-guide.md
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag
from dateutil import parser as dateparser
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ──────────────────────────────────────────────────────────────
# CONFIGURATION — edit these for your environment
# ──────────────────────────────────────────────────────────────

REVIEW_FOLDER_ID = "1HajstYgg_STYYTmLsgcunc-Z2L3EBrRr"
BLOG_FOLDER_ID   = "1lYbX883KgvNHm6VUcOMckOORlbPrVkrW"

SERVICE_ACCOUNT_FILE = (
    Path(__file__).parent / "n8n" / "noted-sled-489022-a2-2d59b1c03f2f.json"
)

SITE_ROOT             = Path(__file__).parent
REVIEW_TEMPLATE_PATH  = SITE_ROOT / "Reviews"   / "_review-template.html"
BLOG_TEMPLATE_PATH    = SITE_ROOT / "BlogPosts" / "_blog-template.html"
REVIEWS_DIR           = SITE_ROOT / "Reviews"
BLOGPOSTS_DIR         = SITE_ROOT / "BlogPosts"
PAPERS_PAGE           = SITE_ROOT / "papers-of-note.html"
INDEX_PAGE            = SITE_ROOT / "index.html"
STATE_FILE            = SITE_ROOT / ".publish_state.json"
LEGACY_STATE_FILE     = SITE_ROOT / ".review_state.json"

DRIVE_SCOPES   = ["https://www.googleapis.com/auth/drive.readonly"]
SITE_BASE_URL  = "https://mdsynapse.org"

VALID_TAG_CLASSES = {"tag-ai", "tag-clinical", "tag-ethics", "tag-future"}
DEFAULT_TAG_CLASS = "tag-ai"
DEFAULT_CATEGORY  = "AI"


# ══════════════════════════════════════════════════════════════
# SHARED — Google auth + Drive
# ══════════════════════════════════════════════════════════════

def get_drive_service():
    if not SERVICE_ACCOUNT_FILE.exists():
        print(f"ERROR: Service account key not found: {SERVICE_ACCOUNT_FILE}")
        sys.exit(1)
    creds = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE), scopes=DRIVE_SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_docs_in_folder(service, folder_id: str) -> list[dict]:
    results = service.files().list(
        q=(
            f"'{folder_id}' in parents"
            " and mimeType='application/vnd.google-apps.document'"
            " and trashed=false"
        ),
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc",
    ).execute()
    return results.get("files", [])


def export_doc_as_html(service, doc_id: str) -> str:
    response = service.files().export(
        fileId=doc_id, mimeType="text/html"
    ).execute()
    return response.decode("utf-8") if isinstance(response, bytes) else response


# ══════════════════════════════════════════════════════════════
# SHARED — state (with one-time migration from .review_state.json)
# ══════════════════════════════════════════════════════════════

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())

    # One-time migration of pre-existing review state
    if LEGACY_STATE_FILE.exists():
        old = json.loads(LEGACY_STATE_FILE.read_text())
        migrated = {"processed": {}}
        for doc_id, info in old.get("processed", {}).items():
            entry = dict(info)
            entry.setdefault("type", "review")
            migrated["processed"][doc_id] = entry
        STATE_FILE.write_text(json.dumps(migrated, indent=2))
        print(f"Migrated {len(migrated['processed'])} entries from "
              f"{LEGACY_STATE_FILE.name} → {STATE_FILE.name}")
        return migrated

    return {"processed": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def mark_processed(state: dict, doc_id: str, slug: str, doc_type: str) -> None:
    state["processed"][doc_id] = {
        "type": doc_type,
        "slug": slug,
        "published_at": datetime.utcnow().isoformat(),
    }
    save_state(state)


# ══════════════════════════════════════════════════════════════
# SHARED — HTML cleaning
# ══════════════════════════════════════════════════════════════

KEEP_TAGS = {
    "p", "strong", "em", "a", "ul", "ol", "li", "h2", "h3", "h4",
    "sup", "sub", "br", "blockquote", "figure", "img", "figcaption", "hr",
}
STRIP_ATTRS = {"style", "id", "class"}
KEEP_IMG_ATTRS = {"src", "alt", "width", "height"}


def clean_element(el: Tag) -> str | None:
    """Return cleaned HTML for one element, or None for empties / unwanted tags."""
    if el.name not in KEEP_TAGS:
        return None

    fresh_soup = BeautifulSoup(str(el), "html.parser")
    root = fresh_soup.find(el.name)
    if root is None:
        return None

    for tag in fresh_soup.find_all(True):
        # Strip presentation attrs (preserve a few on <img>)
        keep = KEEP_IMG_ATTRS if tag.name == "img" else set()
        for attr in list(tag.attrs.keys()):
            if attr in STRIP_ATTRS and attr not in keep:
                del tag[attr]

        # Fix Google redirect hrefs
        if tag.name == "a" and "href" in tag.attrs:
            href = tag["href"]
            if "google.com/url" in href:
                m = re.search(r"[?&]q=([^&]+)", href)
                if m:
                    tag["href"] = unquote(m.group(1))
            tag["target"] = "_blank"
            tag["rel"] = "noopener noreferrer"
            tag["style"] = "color: var(--teal-primary);"

    for span in fresh_soup.find_all("span"):
        span.unwrap()

    if root.name == "p" and not root.get_text(strip=True):
        return None

    return str(root)


def render_section(elements: list[Tag]) -> str:
    """Render a sequence of elements with [CALLOUT]/[QUOTE] markers."""
    parts: list[str] = []
    i = 0
    while i < len(elements):
        el = elements[i]
        text = el.get_text(strip=True)
        if text == "[CALLOUT]":
            inner = _collect_until(elements, i + 1, "[/CALLOUT]")
            i += len(inner) + 2
            cleaned = [c for raw in inner if (c := clean_element(raw))]
            parts.append(
                '<div class="article-callout">\n'
                + "\n".join(cleaned)
                + "\n</div>"
            )
        elif text == "[QUOTE]":
            inner = _collect_until(elements, i + 1, "[/QUOTE]")
            i += len(inner) + 2
            cleaned = [c for raw in inner if (c := clean_element(raw))]
            parts.append(
                '<blockquote class="article-quote">\n'
                + "\n".join(cleaned)
                + "\n</blockquote>"
            )
        else:
            cleaned = clean_element(el)
            if cleaned:
                parts.append(cleaned)
            i += 1
    return "\n\n".join(parts)


def _collect_until(elements: list[Tag], start: int, sentinel: str) -> list[Tag]:
    out = []
    for el in elements[start:]:
        if el.get_text(strip=True) == sentinel:
            break
        out.append(el)
    return out


# ══════════════════════════════════════════════════════════════
# SHARED — template filling
# ══════════════════════════════════════════════════════════════

def fill_template(template: str, values: dict[str, str]) -> str:
    def replace_conditional(m: re.Match) -> str:
        key, content = m.group(1), m.group(2)
        return content.strip() if values.get(key, "").strip() else ""

    result = re.sub(
        r"\{\{#if (\w+)\}\}(.*?)\{\{/if \1\}\}",
        replace_conditional, template, flags=re.DOTALL,
    )
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", value or "")
    return result


def build_article_tag_spans(tags_csv: str) -> str:
    if not tags_csv.strip():
        return ""
    return "\n".join(
        f'<span class="tag">{t.strip()}</span>'
        for t in tags_csv.split(",")
        if t.strip()
    )


def slugify(text: str) -> str:
    """Convert a title to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def estimate_read_time(elements: list[Tag]) -> int:
    """Words ÷ 200, minimum 1 minute."""
    word_count = sum(len(el.get_text().split()) for el in elements)
    return max(1, round(word_count / 200))


# ══════════════════════════════════════════════════════════════
# REVIEW MODE — metadata table + required H2 sections
# ══════════════════════════════════════════════════════════════

REQUIRED_REVIEW_METADATA = [
    "Review Title", "Subtitle", "Paper Title", "Authors",
    "Venue", "Year", "Paper URL", "Category", "Tag Class",
    "Date", "Read Time", "Slug", "Meta Description",
]
SECTION_MAP = {
    "Why This Paper Matters": "WHY_IT_MATTERS",
    "What They Did":          "WHAT_THEY_DID",
    "Key Findings":           "KEY_FINDINGS",
    "What This Means":        "WHAT_THIS_MEANS",
    "Bottom Line":            "BOTTOM_LINE",
    "References":             "REFERENCES",
}
REQUIRED_REVIEW_SECTIONS = [
    "WHY_IT_MATTERS", "WHAT_THEY_DID", "KEY_FINDINGS",
    "WHAT_THIS_MEANS", "BOTTOM_LINE",
]


def parse_metadata_table(soup: BeautifulSoup) -> dict:
    """Extract the first <table> as a key/value map and remove it from the tree."""
    table = soup.find("table")
    if not table:
        return {}
    md = {}
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) >= 2:
            key = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            if key:
                md[key] = value
    table.decompose()
    return md


def collect_review_sections(soup: BeautifulSoup) -> dict[str, list[Tag]]:
    sections: dict[str, list[Tag]] = {}
    current_key, current_elements = None, []
    body = soup.body or soup
    for child in body.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "h2":
            heading_text = child.get_text(strip=True)
            if current_key is not None:
                sections[current_key] = current_elements
            current_key = SECTION_MAP.get(heading_text)
            current_elements = []
        elif current_key is not None:
            current_elements.append(child)
    if current_key is not None and current_elements:
        sections[current_key] = current_elements

    missing = [s for s in REQUIRED_REVIEW_SECTIONS if s not in sections]
    if missing:
        raise ValueError(
            f"Missing required H2 sections: {', '.join(missing)}. "
            "Check heading text matches exactly — see Reviews/_review-guide.md"
        )
    return sections


def split_lead_from_body(elements: list[Tag]) -> tuple[str, str]:
    lead_text, body_els, found_lead = "", [], False
    for el in elements:
        if not found_lead and el.name == "p" and el.get_text(strip=True):
            lead_text = el.get_text(" ", strip=True)
            found_lead = True
        else:
            body_els.append(el)
    return lead_text, render_section(body_els)


# ── papers-of-note.html card injection ───────────────────────

_TAG_STYLES = {
    "tag-ai":       ("rgba(6, 182, 212, 0.1)",  "var(--teal-primary)",  "var(--teal-primary)"),
    "tag-clinical": ("rgba(139, 92, 246, 0.1)", "var(--accent-purple)", "var(--accent-purple)"),
    "tag-ethics":   ("rgba(139, 92, 246, 0.1)", "var(--accent-purple)", "var(--accent-purple)"),
    "tag-future":   ("rgba(244, 63, 94, 0.1)",  "var(--accent-coral)",  "var(--accent-coral)"),
}
_DEFAULT_TAG_STYLE = ("rgba(6, 182, 212, 0.1)", "var(--teal-primary)", "var(--teal-primary)")


def build_papers_card(metadata: dict, first_sentence: str) -> str:
    slug         = metadata["Slug"]
    category     = metadata["Category"]
    paper_url    = metadata["Paper URL"]
    review_title = metadata["Review Title"]
    authors      = metadata["Authors"]
    tag_class    = metadata.get("Tag Class", DEFAULT_TAG_CLASS)
    tag_bg, tag_color, border_color = _TAG_STYLES.get(tag_class, _DEFAULT_TAG_STYLE)
    paper_link_label = "View Paper on arXiv →" if "arxiv.org" in paper_url else "View Paper →"

    return f"""
                    <!-- Paper Card: {review_title} (REVIEW AVAILABLE) -->
                    <article style="background: white; border-radius: 12px; padding: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-left: 4px solid {border_color};">
                        <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
                            <span style="display: inline-block; padding: 0.25rem 0.75rem; background: {tag_bg}; color: {tag_color}; border-radius: 4px; font-size: 0.875rem; font-weight: 500;">{category}</span>
                            <span style="display: inline-block; padding: 0.25rem 0.75rem; background: rgba(63, 209, 193, 0.15); color: var(--teal-primary); border-radius: 4px; font-size: 0.875rem; font-weight: 600;">Review Available</span>
                        </div>
                        <h3 style="font-family: var(--font-display); font-size: 1.5rem; color: var(--navy-dark); margin-bottom: 0.75rem; line-height: 1.4;">
                            {review_title}
                        </h3>
                        <p style="color: var(--gray-dark); margin-bottom: 0.5rem; line-height: 1.6;">
                            <em>{authors}</em>
                        </p>
                        <p style="color: var(--gray-dark); margin-bottom: 1rem; line-height: 1.6;">
                            {first_sentence}
                        </p>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <a href="Reviews/{slug}.html" style="color: var(--teal-primary); text-decoration: none; font-size: 0.875rem; font-weight: 600;">
                                Read Full Review →
                            </a>
                            <a href="{paper_url}" target="_blank" rel="noopener noreferrer" style="color: var(--gray-silver); text-decoration: none; font-size: 0.875rem; font-weight: 500;">
                                {paper_link_label}
                            </a>
                        </div>
                    </article>"""


_PAPERS_CARD_MARKER = '<div style="display: grid; gap: 2rem;">'


def inject_review_card_into_papers_page(card_html: str, slug: str) -> None:
    content = PAPERS_PAGE.read_text(encoding="utf-8")
    if f"Reviews/{slug}.html" in content:
        print(f"  Card for '{slug}' already in {PAPERS_PAGE.name} — skipping injection.")
        return
    idx = content.find(_PAPERS_CARD_MARKER)
    if idx == -1:
        raise ValueError(
            f"Could not find injection marker in {PAPERS_PAGE}: {_PAPERS_CARD_MARKER!r}"
        )
    insert_pos = idx + len(_PAPERS_CARD_MARKER)
    new_content = content[:insert_pos] + "\n" + card_html + "\n" + content[insert_pos:]
    PAPERS_PAGE.write_text(new_content, encoding="utf-8")


def process_review_doc(doc_html: str, dry_run: bool = False) -> str:
    soup = BeautifulSoup(doc_html, "html.parser")

    metadata = parse_metadata_table(soup)
    if not metadata:
        raise ValueError(
            "No metadata table found. Reviews must start with a "
            "two-column key/value table — see Reviews/_review-guide.md"
        )
    missing = [f for f in REQUIRED_REVIEW_METADATA if not metadata.get(f)]
    if missing:
        raise ValueError(f"Missing required metadata fields: {', '.join(missing)}")

    slug = metadata["Slug"]
    print(f"  Title    : {metadata['Review Title']}")
    print(f"  Slug     : {slug}")
    print(f"  Paper    : {metadata['Paper Title']}")

    sections = collect_review_sections(soup)
    why_lead, why_body = split_lead_from_body(sections["WHY_IT_MATTERS"])
    what_they_did     = render_section(sections["WHAT_THEY_DID"])
    key_findings      = render_section(sections["KEY_FINDINGS"])
    what_this_means   = render_section(sections["WHAT_THIS_MEANS"])
    bottom_line       = render_section(sections["BOTTOM_LINE"])
    references        = render_section(sections.get("REFERENCES", []))

    date_obj     = dateparser.parse(metadata["Date"])
    iso_date     = date_obj.strftime("%Y-%m-%d")
    display_date = f"{date_obj.strftime('%B')} {date_obj.day}, {date_obj.year}"

    sentences = why_lead.split(". ")
    first_sentence = sentences[0].rstrip(".") + "." if sentences else ""

    values = {
        "META_DESCRIPTION"    : metadata["Meta Description"],
        "REVIEW_TITLE"        : metadata["Review Title"],
        "SLUG"                : slug,
        "ISO_DATE"            : iso_date,
        "TAG_CLASS"           : metadata.get("Tag Class", DEFAULT_TAG_CLASS),
        "CATEGORY"            : metadata["Category"],
        "SUBTITLE"            : metadata["Subtitle"],
        "DISPLAY_DATE"        : display_date,
        "READ_TIME"           : metadata["Read Time"],
        "PAPER_TITLE"         : metadata["Paper Title"],
        "AUTHORS"             : metadata["Authors"],
        "VENUE"               : metadata["Venue"],
        "YEAR"                : metadata["Year"],
        "PAPER_URL"           : metadata["Paper URL"],
        "WHY_IT_MATTERS_LEAD" : why_lead,
        "WHY_IT_MATTERS_BODY" : why_body,
        "WHAT_THEY_DID"       : what_they_did,
        "KEY_FINDINGS"        : key_findings,
        "WHAT_THIS_MEANS"     : what_this_means,
        "BOTTOM_LINE"         : bottom_line,
        "REFERENCES"          : references,
        "ARTICLE_TAGS"        : build_article_tag_spans(metadata.get("Tags", "")),
    }

    template_text = REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
    output_html   = fill_template(template_text, values)
    card_html     = build_papers_card(metadata, first_sentence)
    output_path   = REVIEWS_DIR / f"{slug}.html"

    if dry_run:
        print(f"\n  [DRY RUN] Would write  : {output_path}")
        print(f"  [DRY RUN] Would update : {PAPERS_PAGE}")
        print(f"\n  ── Card preview ──\n{card_html}")
        print(f"\n  ── URL it would publish to ──")
        print(f"    {SITE_BASE_URL}/Reviews/{slug}.html")
    else:
        output_path.write_text(output_html, encoding="utf-8")
        print(f"  Written  : {output_path}")
        inject_review_card_into_papers_page(card_html, slug)
        print(f"  Updated  : {PAPERS_PAGE}")
        print(f"  Live URL : {SITE_BASE_URL}/Reviews/{slug}.html")

    return slug


# ══════════════════════════════════════════════════════════════
# BLOG MODE — free-form prose
# ══════════════════════════════════════════════════════════════

def collect_blog_body(soup: BeautifulSoup) -> tuple[str, str | None, list[Tag]]:
    """
    Extract (title, subtitle_or_None, body_elements) from the doc.

    Title  = text of the first <h1> (Google Docs export wraps Title style as <h1>).
    Subtitle = text of the next <h2> if it appears before any body paragraph,
               OR text of the first <p> if it is fully italic.
    Body   = everything after the title (and subtitle if extracted).
    """
    body = soup.body or soup
    children = [c for c in body.children if isinstance(c, Tag)]

    title, subtitle = None, None
    body_start = 0

    # Find first <h1>
    for i, el in enumerate(children):
        if el.name == "h1" and el.get_text(strip=True):
            title = el.get_text(" ", strip=True)
            body_start = i + 1
            break

    if title is None:
        raise ValueError(
            "Blog post must have a title styled as Heading 1 (top of doc). "
            "In Google Docs: Format → Paragraph styles → Heading 1."
        )

    # Optional subtitle: next non-empty element if it's an h2 OR a fully-italic <p>
    while body_start < len(children):
        el = children[body_start]
        text = el.get_text(strip=True)
        if not text:
            body_start += 1
            continue
        if el.name == "h2":
            subtitle = text
            body_start += 1
        elif el.name == "p":
            # Fully italic paragraph counts as subtitle
            inner_text = el.get_text(strip=True)
            italic_text = "".join(t.get_text(strip=True) for t in el.find_all(["em", "i"]))
            if inner_text and italic_text == inner_text:
                subtitle = inner_text
                body_start += 1
        break

    return title, subtitle, children[body_start:]


def build_index_card(values: dict, excerpt: str) -> str:
    """Build an article-card matching index.html's articles-grid markup."""
    tag_class = values["TAG_CLASS"]
    category  = values["CATEGORY"]
    title     = values["TITLE"]
    slug      = values["SLUG"]
    read_time = values["READ_TIME"]
    return (
        '                <article class="article-card">\n'
        f'                    <div class="article-tag {tag_class}">{category}</div>\n'
        f'                    <h3 class="article-title">{title}</h3>\n'
        f'                    <p class="article-excerpt">{excerpt}</p>\n'
        '                    <div class="article-meta">\n'
        f'                        <span class="read-time">{read_time} min read</span>\n'
        f'                        <a href="BlogPosts/{slug}.html" class="article-link">Read more →</a>\n'
        '                    </div>\n'
        '                </article>'
    )


_INDEX_GRID_OPEN  = '<div class="articles-grid">'


def inject_blog_card_into_index(card_html: str, slug: str) -> None:
    content = INDEX_PAGE.read_text(encoding="utf-8")
    if f'BlogPosts/{slug}.html' in content:
        print(f"  Card for '{slug}' already in {INDEX_PAGE.name} — skipping injection.")
        return
    idx = content.find(_INDEX_GRID_OPEN)
    if idx == -1:
        raise ValueError(
            f"Could not find articles-grid marker in {INDEX_PAGE}: {_INDEX_GRID_OPEN!r}"
        )
    insert_pos = idx + len(_INDEX_GRID_OPEN)
    new_content = (
        content[:insert_pos] + "\n" + card_html + "\n" + content[insert_pos:]
    )
    INDEX_PAGE.write_text(new_content, encoding="utf-8")


def process_blog_doc(doc_html: str, doc_meta: dict | None, dry_run: bool = False) -> str:
    """
    Parse and publish a blog post.

    doc_meta = {'modifiedTime': str} from Drive (used as fallback date). Optional.
    """
    soup = BeautifulSoup(doc_html, "html.parser")

    # Optional metadata table at the top — overrides defaults if present
    md = parse_metadata_table(soup)
    title_from_md = md.get("Title")

    # Title / subtitle / body from the document structure
    inferred_title, subtitle, body_elements = collect_blog_body(soup)
    title = title_from_md or inferred_title

    # Compute defaults; metadata table overrides
    slug         = md.get("Slug")          or slugify(title)
    category     = md.get("Category")      or DEFAULT_CATEGORY
    tag_class    = md.get("Tag Class")     or DEFAULT_TAG_CLASS
    if tag_class not in VALID_TAG_CLASSES:
        print(f"  WARNING: Tag Class '{tag_class}' is not one of "
              f"{sorted(VALID_TAG_CLASSES)} — using {DEFAULT_TAG_CLASS}.")
        tag_class = DEFAULT_TAG_CLASS

    subtitle     = md.get("Subtitle")      or subtitle or ""
    read_time    = md.get("Read Time")     or str(estimate_read_time(body_elements))

    # Date: metadata > doc modifiedTime > today
    date_str = md.get("Date") or (doc_meta or {}).get("modifiedTime")
    date_obj = dateparser.parse(date_str) if date_str else datetime.utcnow()
    iso_date     = date_obj.strftime("%Y-%m-%d")
    display_date = f"{date_obj.strftime('%B')} {date_obj.day}, {date_obj.year}"

    # Body / lead split: first non-empty <p> becomes the styled lead
    lead_text = ""
    rest = list(body_elements)
    for i, el in enumerate(rest):
        if el.name == "p" and el.get_text(strip=True):
            lead_text = el.get_text(" ", strip=True)
            rest = rest[i + 1:]
            break

    body_html = render_section(rest)

    # Excerpt for index card: meta description override > lead > first body sentence
    excerpt = md.get("Meta Description") or lead_text
    if not excerpt and rest:
        first_p = next((e for e in rest if e.name == "p"), None)
        if first_p:
            excerpt = first_p.get_text(" ", strip=True)
    excerpt = (excerpt or "").strip()
    if len(excerpt) > 240:
        excerpt = excerpt[:237].rstrip() + "…"

    meta_description = md.get("Meta Description") or excerpt[:160]

    print(f"  Title    : {title}")
    print(f"  Slug     : {slug}")
    print(f"  Category : {category} ({tag_class})")
    print(f"  Date     : {display_date}")
    print(f"  Read time: {read_time} min")

    values = {
        "TITLE"            : title,
        "SUBTITLE"         : subtitle,
        "SLUG"             : slug,
        "CATEGORY"         : category,
        "TAG_CLASS"        : tag_class,
        "ISO_DATE"         : iso_date,
        "DISPLAY_DATE"     : display_date,
        "READ_TIME"        : read_time,
        "META_DESCRIPTION" : meta_description,
        "LEAD"             : lead_text,
        "BODY"             : body_html,
    }

    template_text = BLOG_TEMPLATE_PATH.read_text(encoding="utf-8")
    output_html   = fill_template(template_text, values)
    card_html     = build_index_card(values, excerpt)
    output_path   = BLOGPOSTS_DIR / f"{slug}.html"

    if dry_run:
        print(f"\n  [DRY RUN] Would write  : {output_path}")
        print(f"  [DRY RUN] Would update : {INDEX_PAGE}")
        print(f"\n  ── Card preview ──\n{card_html}")
        print(f"\n  ── URL it would publish to ──")
        print(f"    {SITE_BASE_URL}/BlogPosts/{slug}.html")
    else:
        output_path.write_text(output_html, encoding="utf-8")
        print(f"  Written  : {output_path}")
        inject_blog_card_into_index(card_html, slug)
        print(f"  Updated  : {INDEX_PAGE}")
        print(f"  Live URL : {SITE_BASE_URL}/BlogPosts/{slug}.html")

    return slug


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def prompt_for_mode() -> str:
    while True:
        choice = input("\nPublish (r)eviews or (b)log posts? [r/b]: ").strip().lower()
        if choice in {"r", "review", "reviews"}:
            return "review"
        if choice in {"b", "blog", "blogs"}:
            return "blog"
        print("  Please enter 'r' or 'b'.")


def run(args: argparse.Namespace) -> None:
    mode = args.mode or prompt_for_mode()

    if mode == "review":
        folder_id      = REVIEW_FOLDER_ID
        process_doc_fn = lambda html, meta: process_review_doc(html, dry_run=args.dry_run)
        kind_label     = "review"
    else:
        folder_id      = BLOG_FOLDER_ID
        process_doc_fn = lambda html, meta: process_blog_doc(html, meta, dry_run=args.dry_run)
        kind_label     = "blog post"

    service = get_drive_service()
    state   = load_state()

    if args.doc_id:
        docs_to_process = [{"id": args.doc_id, "name": f"(doc-id: {args.doc_id})", "modifiedTime": None}]
    else:
        all_docs = list_docs_in_folder(service, folder_id)
        if args.reprocess:
            docs_to_process = all_docs
        else:
            docs_to_process = [d for d in all_docs if d["id"] not in state["processed"]]
        print(f"Found {len(all_docs)} doc(s) in {kind_label} folder — "
              f"{len(docs_to_process)} to process.")

    if not docs_to_process:
        print("Nothing to do.")
        return

    success, failed = 0, 0
    for doc in docs_to_process:
        print(f"\n{'─'*60}")
        print(f"{kind_label.capitalize()}: {doc['name']} ({doc['id']})")
        try:
            doc_html = export_doc_as_html(service, doc["id"])
            slug = process_doc_fn(doc_html, doc)
            if not args.dry_run:
                mark_processed(state, doc["id"], slug, mode)
            success += 1
        except (ValueError, HttpError) as e:
            print(f"  ERROR: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            failed += 1

    print(f"\n{'─'*60}")
    print(f"Done. {success} published, {failed} failed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish Google Docs to NeoSynapse (reviews or blog posts).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Interactive — script asks review or blog
  uv run publish.py

  # All new blog posts in the blog Drive folder
  uv run publish.py --mode blog

  # All new reviews
  uv run publish.py --mode review

  # One specific doc by ID
  uv run publish.py --mode blog --doc-id 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms

  # Preview without writing files
  uv run publish.py --mode blog --doc-id DOC_ID --dry-run

  # Re-publish an already-processed doc
  uv run publish.py --mode review --doc-id DOC_ID --reprocess
        """,
    )
    parser.add_argument("--mode",      choices=["review", "blog"],
                        help="Which pipeline to run. Omit for interactive prompt.")
    parser.add_argument("--doc-id",    help="Process a specific Google Doc by ID")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Parse and preview without writing")
    parser.add_argument("--reprocess", action="store_true",
                        help="Re-publish already-processed docs")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print full tracebacks on error")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
