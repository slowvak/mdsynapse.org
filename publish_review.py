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
publish_review.py — Convert Google Docs paper reviews into NeoSynapse HTML pages.

Workflow:
  1. Scan a Google Drive folder for Google Docs not yet published
  2. Export each doc as HTML via Drive API
  3. Parse metadata table + section headings from the exported HTML
  4. Fill Reviews/_review-template.html with the parsed content
  5. Write Reviews/{slug}.html
  6. Inject a card into papers-of-note.html (newest first)
  7. Record the doc ID in .review_state.json so it won't be reprocessed

Google Doc format: see Reviews/_review-guide.md

Usage:
  uv run publish_review.py                        # process all new docs in folder
  uv run publish_review.py --doc-id DOC_ID        # process one specific doc
  uv run publish_review.py --doc-id DOC_ID --dry-run
  uv run publish_review.py --reprocess --doc-id DOC_ID

Setup (one-time):
  1. Set REVIEW_FOLDER_ID below to your Google Drive folder ID
  2. Confirm SERVICE_ACCOUNT_FILE points to your key JSON
  3. Share the Drive folder with the service account email
"""

import argparse
import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup, NavigableString, Tag
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ──────────────────────────────────────────────────────────────
# CONFIGURATION — edit these for your environment
# ──────────────────────────────────────────────────────────────

# Google Drive folder containing paper review Docs
# Get this from the folder URL: drive.google.com/drive/folders/<FOLDER_ID>
REVIEW_FOLDER_ID = "1HajstYgg_STYYTmLsgcunc-Z2L3EBrRr"

# Path to your service account JSON key
# This file is already set up at: n8n/noted-sled-489022-a2-2d59b1c03f2f.json
SERVICE_ACCOUNT_FILE = Path(__file__).parent / "n8n" / "noted-sled-489022-a2-2d59b1c03f2f.json"

# Paths (relative to this script's location)
SITE_ROOT        = Path(__file__).parent
TEMPLATE_PATH    = SITE_ROOT / "Reviews" / "_review-template.html"
REVIEWS_DIR      = SITE_ROOT / "Reviews"
PAPERS_PAGE      = SITE_ROOT / "papers-of-note.html"
STATE_FILE       = SITE_ROOT / ".review_state.json"

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


# ──────────────────────────────────────────────────────────────
# GOOGLE AUTH + DRIVE
# ──────────────────────────────────────────────────────────────

def get_drive_service():
    if not SERVICE_ACCOUNT_FILE.exists():
        print(f"ERROR: Service account key not found: {SERVICE_ACCOUNT_FILE}")
        sys.exit(1)
    creds = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE), scopes=DRIVE_SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_docs_in_folder(service, folder_id: str) -> list[dict]:
    """Return [{id, name, modifiedTime}] for all Google Docs in the folder."""
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
    """Export a Google Doc as an HTML string."""
    response = service.files().export(
        fileId=doc_id,
        mimeType="text/html",
    ).execute()
    return response.decode("utf-8") if isinstance(response, bytes) else response


# ──────────────────────────────────────────────────────────────
# STATE MANAGEMENT
# ──────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"processed": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def mark_processed(state: dict, doc_id: str, slug: str) -> None:
    state["processed"][doc_id] = {
        "slug": slug,
        "published_at": datetime.utcnow().isoformat(),
    }
    save_state(state)


# ──────────────────────────────────────────────────────────────
# HTML PARSING — metadata table
# ──────────────────────────────────────────────────────────────

REQUIRED_METADATA = [
    "Review Title", "Subtitle", "Paper Title", "Authors",
    "Venue", "Year", "Paper URL", "Category", "Tag Class",
    "Date", "Read Time", "Slug", "Meta Description",
]

OPTIONAL_METADATA = ["Tags"]


def parse_metadata_table(soup: BeautifulSoup) -> dict:
    """
    Extract key/value pairs from the first <table> in the exported doc.
    Returns {field_name: value_string}.
    """
    table = soup.find("table")
    if not table:
        raise ValueError(
            "No metadata table found. The Google Doc must start with a "
            "two-column key/value table — see Reviews/_review-guide.md"
        )

    metadata = {}
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) >= 2:
            key = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            if key:
                metadata[key] = value

    missing = [f for f in REQUIRED_METADATA if not metadata.get(f)]
    if missing:
        raise ValueError(f"Missing required metadata fields: {', '.join(missing)}")

    # Remove the table from the soup so it doesn't appear in section content
    table.decompose()

    return metadata


# ──────────────────────────────────────────────────────────────
# HTML PARSING — section extraction
# ──────────────────────────────────────────────────────────────

# Map exact H2 heading text → internal key
SECTION_MAP = {
    "Why This Paper Matters": "WHY_IT_MATTERS",
    "What They Did":          "WHAT_THEY_DID",
    "Key Findings":           "KEY_FINDINGS",
    "What This Means":        "WHAT_THIS_MEANS",
    "Bottom Line":            "BOTTOM_LINE",
    "References":             "REFERENCES",
}

REQUIRED_SECTIONS = ["WHY_IT_MATTERS", "WHAT_THEY_DID", "KEY_FINDINGS", "WHAT_THIS_MEANS", "BOTTOM_LINE"]


def collect_sections(soup: BeautifulSoup) -> dict[str, list[Tag]]:
    """
    Split the document body at H2 boundaries into named sections.
    Returns {section_key: [list_of_Tag_elements]}.
    """
    sections: dict[str, list[Tag]] = {}
    current_key = None
    current_elements: list[Tag] = []

    body = soup.body or soup
    for child in body.children:
        if not isinstance(child, Tag):
            continue

        if child.name == "h2":
            heading_text = child.get_text(strip=True)
            # Save previous section
            if current_key is not None:
                sections[current_key] = current_elements
            current_key = SECTION_MAP.get(heading_text)
            current_elements = []
        elif current_key is not None:
            current_elements.append(child)

    # Flush last section
    if current_key is not None and current_elements:
        sections[current_key] = current_elements

    missing = [s for s in REQUIRED_SECTIONS if s not in sections]
    if missing:
        raise ValueError(
            f"Missing required H2 sections: {', '.join(missing)}. "
            "Check heading text matches exactly — see Reviews/_review-guide.md"
        )

    return sections


# ──────────────────────────────────────────────────────────────
# HTML CLEANING
# ──────────────────────────────────────────────────────────────

KEEP_TAGS = {"p", "strong", "em", "a", "ul", "ol", "li", "h3", "h4", "sup", "sub", "br"}
STRIP_ATTRS = {"style", "id", "class"}


def clean_element(el: Tag) -> str | None:
    """
    Return a cleaned HTML string for a single top-level element, or None
    if the element is empty or not a meaningful tag.

    Cleans: removes style/id/class, unwraps <span>s, fixes Google redirect URLs.
    """
    if el.name not in KEEP_TAGS:
        return None

    # Work on a fresh parse to avoid mutating the original tree
    fresh_soup = BeautifulSoup(str(el), "html.parser")
    root = fresh_soup.find(el.name)
    if root is None:
        return None

    # Strip presentation attributes from all descendants
    for tag in fresh_soup.find_all(True):
        for attr in list(tag.attrs.keys()):
            if attr in STRIP_ATTRS:
                del tag[attr]

        # Fix Google-wrapped redirect URLs
        if tag.name == "a" and "href" in tag.attrs:
            href = tag["href"]
            if "google.com/url" in href:
                m = re.search(r"[?&]q=([^&]+)", href)
                if m:
                    tag["href"] = unquote(m.group(1))
            tag["target"] = "_blank"
            tag["rel"] = "noopener noreferrer"
            tag["style"] = "color: var(--teal-primary);"

    # Unwrap <span> elements (preserve their text/children)
    for span in fresh_soup.find_all("span"):
        span.unwrap()

    # Drop empty paragraphs
    if root.name == "p" and not root.get_text(strip=True):
        return None

    return str(root)


# ──────────────────────────────────────────────────────────────
# SECTION RENDERING — callout/quote markers
# ──────────────────────────────────────────────────────────────

def render_section(elements: list[Tag]) -> str:
    """
    Convert a list of section elements to an HTML string.

    Handles [CALLOUT]...[/CALLOUT] and [QUOTE]...[/QUOTE] markers.
    Each marker must appear as its own paragraph in the Google Doc.
    """
    parts: list[str] = []
    i = 0

    while i < len(elements):
        el = elements[i]
        text = el.get_text(strip=True)

        if text == "[CALLOUT]":
            inner = _collect_until(elements, i + 1, "[/CALLOUT]")
            i += len(inner) + 2  # skip opener, content, closer
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
    """Return elements[start:] up to (but not including) the sentinel paragraph."""
    collected = []
    for el in elements[start:]:
        if el.get_text(strip=True) == sentinel:
            break
        collected.append(el)
    return collected


def split_lead_from_body(elements: list[Tag]) -> tuple[str, str]:
    """
    For 'Why This Paper Matters': split into lead (first non-empty <p>) and body.
    Returns (lead_plain_text, body_html).
    The lead is extracted as plain text so it's injected into the template's
    <p class="lead"> wrapper without an extra <p> tag.
    """
    lead_text = ""
    body_els: list[Tag] = []
    found_lead = False

    for el in elements:
        if not found_lead and el.name == "p" and el.get_text(strip=True):
            lead_text = el.get_text(" ", strip=True)
            found_lead = True
        else:
            body_els.append(el)

    return lead_text, render_section(body_els)


# ──────────────────────────────────────────────────────────────
# TEMPLATE FILLING
# ──────────────────────────────────────────────────────────────

def fill_template(template: str, values: dict[str, str]) -> str:
    """
    Replace {{KEY}} tokens and process {{#if KEY}}...{{/if KEY}} blocks.
    """
    # Conditionals
    def replace_conditional(m: re.Match) -> str:
        key, content = m.group(1), m.group(2)
        return content.strip() if values.get(key, "").strip() else ""

    result = re.sub(
        r"\{\{#if (\w+)\}\}(.*?)\{\{/if \1\}\}",
        replace_conditional,
        template,
        flags=re.DOTALL,
    )

    # Simple token replacement
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", value or "")

    return result


def build_article_tag_spans(tags_csv: str) -> str:
    """'AI, Fairness, EHR' → HTML spans for the article footer."""
    if not tags_csv.strip():
        return ""
    return "\n".join(
        f'<span class="tag">{t.strip()}</span>'
        for t in tags_csv.split(",")
        if t.strip()
    )


# ──────────────────────────────────────────────────────────────
# papers-of-note.html CARD INJECTION
# ──────────────────────────────────────────────────────────────

# Inline style values matching the site palette
_TAG_STYLES = {
    "tag-ai":       ("rgba(6, 182, 212, 0.1)",   "var(--teal-primary)",   "var(--teal-primary)"),
    "tag-clinical": ("rgba(139, 92, 246, 0.1)",  "var(--accent-purple)",  "var(--accent-purple)"),
    "tag-ethics":   ("rgba(139, 92, 246, 0.1)",  "var(--accent-purple)",  "var(--accent-purple)"),
    "tag-future":   ("rgba(244, 63, 94, 0.1)",   "var(--accent-coral)",   "var(--accent-coral)"),
}
_DEFAULT_TAG_STYLE = ("rgba(6, 182, 212, 0.1)", "var(--teal-primary)", "var(--teal-primary)")


def build_papers_card(metadata: dict, first_sentence: str) -> str:
    slug         = metadata["Slug"]
    category     = metadata["Category"]
    paper_url    = metadata["Paper URL"]
    review_title = metadata["Review Title"]
    authors      = metadata["Authors"]
    tag_class    = metadata.get("Tag Class", "tag-ai")

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


# The comment that marks where cards begin in the papers page
_CARD_GRID_MARKER = '<div style="display: grid; gap: 2rem;">'


def inject_card_into_papers_page(card_html: str, slug: str) -> None:
    """
    Insert card_html as the first item in the Paper Cards grid.
    Skips injection if a card for this slug already exists.
    """
    content = PAPERS_PAGE.read_text(encoding="utf-8")

    # Guard against duplicate injection on reprocess
    if f"Reviews/{slug}.html" in content:
        print(f"  Card for '{slug}' already exists in papers-of-note.html — skipping injection.")
        return

    idx = content.find(_CARD_GRID_MARKER)
    if idx == -1:
        raise ValueError(
            f"Could not find injection marker in {PAPERS_PAGE}. "
            f"Expected: {_CARD_GRID_MARKER!r}"
        )

    insert_pos = idx + len(_CARD_GRID_MARKER)
    new_content = content[:insert_pos] + "\n" + card_html + "\n" + content[insert_pos:]
    PAPERS_PAGE.write_text(new_content, encoding="utf-8")


# ──────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ──────────────────────────────────────────────────────────────

def process_doc(doc_html: str, dry_run: bool = False) -> str:
    """
    Parse a Google Doc HTML export and publish it.
    Returns the slug of the published review.
    """
    soup = BeautifulSoup(doc_html, "html.parser")

    # ── 1. Metadata ──
    metadata = parse_metadata_table(soup)
    slug = metadata["Slug"]
    print(f"  Title    : {metadata['Review Title']}")
    print(f"  Slug     : {slug}")
    print(f"  Paper    : {metadata['Paper Title']}")

    # ── 2. Sections ──
    sections = collect_sections(soup)

    # ── 3. Render sections ──
    why_lead, why_body   = split_lead_from_body(sections["WHY_IT_MATTERS"])
    what_they_did        = render_section(sections["WHAT_THEY_DID"])
    key_findings         = render_section(sections["KEY_FINDINGS"])
    what_this_means      = render_section(sections["WHAT_THIS_MEANS"])
    bottom_line          = render_section(sections["BOTTOM_LINE"])
    references           = render_section(sections.get("REFERENCES", []))

    # ── 4. Dates ──
    from dateutil import parser as dateparser
    date_obj    = dateparser.parse(metadata["Date"])
    iso_date    = date_obj.strftime("%Y-%m-%d")
    display_date = f"{date_obj.strftime('%B')} {date_obj.day}, {date_obj.year}"

    # ── 5. Build template values ──
    # First sentence of the lede for the papers-of-note card
    sentences = why_lead.split(". ")
    first_sentence = sentences[0].rstrip(".") + "." if sentences else ""

    values = {
        "META_DESCRIPTION" : metadata["Meta Description"],
        "REVIEW_TITLE"     : metadata["Review Title"],
        "SLUG"             : slug,
        "ISO_DATE"         : iso_date,
        "TAG_CLASS"        : metadata.get("Tag Class", "tag-ai"),
        "CATEGORY"         : metadata["Category"],
        "SUBTITLE"         : metadata["Subtitle"],
        "DISPLAY_DATE"     : display_date,
        "READ_TIME"        : metadata["Read Time"],
        "PAPER_TITLE"      : metadata["Paper Title"],
        "AUTHORS"          : metadata["Authors"],
        "VENUE"            : metadata["Venue"],
        "YEAR"             : metadata["Year"],
        "PAPER_URL"        : metadata["Paper URL"],
        "WHY_IT_MATTERS_LEAD" : why_lead,
        "WHY_IT_MATTERS_BODY" : why_body,
        "WHAT_THEY_DID"    : what_they_did,
        "KEY_FINDINGS"     : key_findings,
        "WHAT_THIS_MEANS"  : what_this_means,
        "BOTTOM_LINE"      : bottom_line,
        "REFERENCES"       : references,
        "ARTICLE_TAGS"     : build_article_tag_spans(metadata.get("Tags", "")),
    }

    # ── 6. Fill template ──
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    output_html   = fill_template(template_text, values)

    # ── 7. Build card ──
    card_html = build_papers_card(metadata, first_sentence)

    # ── 8. Write (or preview) ──
    output_path = REVIEWS_DIR / f"{slug}.html"

    if dry_run:
        print(f"\n  [DRY RUN] Would write  : {output_path}")
        print(f"  [DRY RUN] Would update : {PAPERS_PAGE}")
        print(f"\n  ── Card preview ──\n{card_html}\n")
        print(f"\n  ── Template keys filled ──")
        for k, v in values.items():
            preview = (v[:80] + "…") if len(v) > 80 else v
            print(f"    {k:30s}: {preview!r}")
    else:
        output_path.write_text(output_html, encoding="utf-8")
        print(f"  Written  : {output_path}")
        inject_card_into_papers_page(card_html, slug)
        print(f"  Updated  : {PAPERS_PAGE}")

    return slug


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    if REVIEW_FOLDER_ID == "YOUR_GOOGLE_DRIVE_FOLDER_ID" and not args.doc_id:
        print("ERROR: Set REVIEW_FOLDER_ID at the top of publish_review.py")
        sys.exit(1)

    service = get_drive_service()
    state   = load_state()

    if args.doc_id:
        docs_to_process = [{"id": args.doc_id, "name": f"(doc-id: {args.doc_id})"}]
    else:
        all_docs = list_docs_in_folder(service, REVIEW_FOLDER_ID)
        if args.reprocess:
            docs_to_process = all_docs
        else:
            docs_to_process = [d for d in all_docs if d["id"] not in state["processed"]]
        print(f"Found {len(all_docs)} doc(s) in folder — {len(docs_to_process)} to process.")

    if not docs_to_process:
        print("Nothing to do.")
        return

    success, failed = 0, 0
    for doc in docs_to_process:
        print(f"\n{'─'*60}")
        print(f"Doc: {doc['name']} ({doc['id']})")
        try:
            doc_html = export_doc_as_html(service, doc["id"])
            slug = process_doc(doc_html, dry_run=args.dry_run)
            if not args.dry_run:
                mark_processed(state, doc["id"], slug)
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
        description="Publish Google Docs paper reviews to NeoSynapse.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Scan folder, publish anything new
  uv run publish_review.py

  # Publish one specific doc (get ID from its Google Drive URL)
  uv run publish_review.py --doc-id 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms

  # Preview without writing files
  uv run publish_review.py --doc-id DOC_ID --dry-run

  # Re-publish an already-processed doc (overwrites existing HTML)
  uv run publish_review.py --doc-id DOC_ID --reprocess
        """,
    )
    parser.add_argument("--doc-id",    help="Process a specific Google Doc by ID")
    parser.add_argument("--dry-run",   action="store_true", help="Parse and preview without writing")
    parser.add_argument("--reprocess", action="store_true", help="Re-publish already-processed docs")
    parser.add_argument("--verbose",   "-v", action="store_true", help="Print full tracebacks on error")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
