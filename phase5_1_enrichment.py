"""
Phase 5.1 — Public Professional Enrichment
============================================

Purpose
-------
Enrich validated Phase 5 CXO/leadership records using ONLY public,
company-owned web pages.

Cost policy
-----------
Google Places API : NOT USED
Google Search API  : NOT USED
Paid API           : NOT USED
Proxy              : NOT USED
Scraping service   : NOT USED

Input
-----
output/cxo/cxo_people_final.csv

Output
------
output/cxo/cxo_people_enriched.csv

Important
---------
This phase does NOT search the open web.

For each person it:
1. Uses the existing company-owned source_url.
2. Fetches that public page with normal HTTP requests.
3. Examines links on the same company domain.
4. Scores likely person/profile/bio links using the person's name.
5. Extracts a small amount of public professional evidence.
6. Preserves the original Phase 5 data.
7. Never invents a profile URL, location, email, phone, or biography.

If a site returns 403/401/429 or otherwise blocks the request, the record
is retained with an explicit enrichment status.
"""

from __future__ import annotations

import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests import Response
from requests.exceptions import RequestException

INPUT_FILE = Path("output/cxo/cxo_people_final.csv")
OUTPUT_FILE = Path("output/cxo/cxo_people_enriched.csv")

REQUEST_TIMEOUT = 20
REQUEST_DELAY_SECONDS = 0.75
MAX_PROFILE_LINKS_TO_INSPECT = 8

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0 Safari/537.36"
)

PROFILE_PATH_TERMS = (
    "leadership",
    "management",
    "executive",
    "profile",
    "bio",
    "biography",
    "about",
    "team",
    "people",
    "directors",
)

IGNORE_PATH_TERMS = (
    "privacy",
    "cookie",
    "terms",
    "careers",
    "job",
    "login",
    "signin",
    "contact",
    "investor-relations",
    "news",
    "press",
    "media",
)

ROLE_TERMS = (
    "chief",
    "officer",
    "ceo",
    "coo",
    "cfo",
    "cio",
    "cto",
    "cmo",
    "chro",
    "president",
    "director",
    "chairman",
    "chairperson",
    "managing director",
    "vice president",
    "founder",
    "secretary",
    "general counsel",
)


# ---------------------------------------------------------------------
# Text / URL helpers
# ---------------------------------------------------------------------


def clean_text(value: object) -> str:
    """Normalize whitespace."""
    text = "" if value is None else str(value)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(value: object) -> str:
    """Accept only absolute HTTP(S) URLs."""
    value = clean_text(value)

    if not value:
        return ""

    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"}:
        return ""

    if not parsed.netloc:
        return ""

    return value.rstrip("/")


def hostname(value: str) -> str:
    """Return a normalized hostname."""
    parsed = urlparse(value)

    host = parsed.hostname or ""

    return host.casefold().removeprefix("www.")


def same_company_domain(
    candidate_url: str,
    source_url: str,
) -> bool:
    """Check that a candidate link belongs to the same company domain."""
    candidate_host = hostname(candidate_url)
    source_host = hostname(source_url)

    if not candidate_host or not source_host:
        return False

    return (
        candidate_host == source_host
        or candidate_host.endswith("." + source_host)
        or source_host.endswith("." + candidate_host)
    )


def name_tokens(name: str) -> list[str]:
    """Return meaningful alphabetic tokens from a person's name."""
    tokens = re.findall(
        r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}",
        clean_text(name),
    )

    stop_words = {
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "sir",
        "the",
    }

    return [token.casefold() for token in tokens if token.casefold() not in stop_words]


def name_match_score(
    person_name: str,
    candidate_text: str,
) -> int:
    """Score how strongly a candidate link matches the person name."""
    tokens = name_tokens(person_name)

    if not tokens:
        return 0

    haystack = clean_text(candidate_text).casefold()

    matched = sum(1 for token in tokens if token in haystack)

    if matched == len(tokens):
        return 70

    if matched >= 2:
        return 50

    if matched == 1:
        return 20

    return 0


def path_score(candidate_url: str) -> int:
    """Score URL paths likely to contain professional profiles."""
    parsed = urlparse(candidate_url)
    path = parsed.path.casefold()

    score = 0

    for term in PROFILE_PATH_TERMS:
        if term in path:
            score += 12

    for term in IGNORE_PATH_TERMS:
        if term in path:
            score -= 20

    return max(score, 0)


GENERIC_ANCHOR_FRAGMENTS = {
    "",
    "#",
    "#main",
    "#main-content",
    "#content",
    "#skip",
    "#skip-to-content",
    "#top",
}


def is_generic_page_anchor(candidate_url: str) -> bool:
    """Reject generic same-page navigation anchors."""
    fragment = urlparse(candidate_url).fragment.casefold()
    return fragment in {value.casefold() for value in GENERIC_ANCHOR_FRAGMENTS}


def looks_like_profile_url(
    candidate_url: str,
    person_name: str,
) -> bool:
    """Require a plausible profile path and name evidence."""
    parsed = urlparse(candidate_url)
    path = parsed.path.casefold()

    if is_generic_page_anchor(candidate_url):
        return False

    if not any(term in path for term in PROFILE_PATH_TERMS):
        return False

    tokens = name_tokens(person_name)
    if not tokens:
        return False

    normalized_path = re.sub(
        r"[^a-z0-9]+",
        "-",
        path,
    )

    return any(token in normalized_path for token in tokens)


def role_match_score(
    designation: str,
    candidate_text: str,
) -> int:
    """Score candidate text against the known designation."""
    designation = clean_text(designation).casefold()
    candidate = clean_text(candidate_text).casefold()

    if not designation or not candidate:
        return 0

    exact = designation in candidate

    if exact:
        return 35

    matched_terms = sum(
        1 for term in ROLE_TERMS if term in designation and term in candidate
    )

    return min(matched_terms * 8, 25)


# ---------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------


def create_session() -> requests.Session:
    """Create a conservative normal HTTP session."""
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml," "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "keep-alive",
        }
    )

    return session


def fetch_page(
    session: requests.Session,
    url: str,
) -> tuple[Response | None, str]:
    """Fetch a public page and return response plus status description."""
    try:
        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
    except RequestException as error:
        return None, f"request_error:{type(error).__name__}"

    if response.status_code == 403:
        return response, "blocked_403"

    if response.status_code == 401:
        return response, "blocked_401"

    if response.status_code == 429:
        return response, "rate_limited_429"

    if response.status_code >= 400:
        return response, f"http_error_{response.status_code}"

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).casefold()

    if "html" not in content_type:
        return response, "non_html"

    return response, "ok"


# ---------------------------------------------------------------------
# Public company-owned page analysis
# ---------------------------------------------------------------------


def extract_page_text(
    soup: BeautifulSoup,
) -> str:
    """Extract visible text from a page."""
    for element in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
        ]
    ):
        element.decompose()

    return clean_text(soup.get_text(" ", strip=True))


def find_candidate_profile_links(
    soup: BeautifulSoup,
    person_name: str,
    designation: str,
    source_url: str,
) -> list[dict[str, object]]:
    """
    Find likely professional profile links on the same company domain.

    No external domains are accepted.
    """
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        href = clean_text(anchor.get("href", ""))

        if not href:
            continue

        candidate_url = normalize_url(urljoin(source_url, href))

        if not candidate_url:
            continue

        if candidate_url in seen:
            continue

        seen.add(candidate_url)

        if not same_company_domain(
            candidate_url,
            source_url,
        ):
            continue

        if not looks_like_profile_url(
            candidate_url,
            person_name,
        ):
            continue

        anchor_text = clean_text(anchor.get_text(" ", strip=True))

        context_parent = anchor.parent

        context = anchor_text

        if context_parent is not None:
            context = clean_text(
                context_parent.get_text(
                    " ",
                    strip=True,
                )
            )

        score = 0
        score += name_match_score(
            person_name,
            anchor_text,
        )
        score += (
            name_match_score(
                person_name,
                context,
            )
            // 2
        )
        score += path_score(candidate_url)
        score += role_match_score(
            designation,
            context,
        )

        if score <= 0:
            continue

        candidates.append(
            {
                "url": candidate_url,
                "anchor_text": anchor_text,
                "context": context[:500],
                "score": min(score, 100),
            }
        )

    candidates.sort(
        key=lambda item: int(item["score"]),
        reverse=True,
    )

    return candidates[:MAX_PROFILE_LINKS_TO_INSPECT]


def choose_best_profile(
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    """Return the strongest candidate only when evidence is meaningful."""
    if not candidates:
        return None

    best = candidates[0]

    if int(best["score"]) < 55:
        return None

    return best


def extract_public_bio(
    soup: BeautifulSoup,
    person_name: str,
    designation: str,
) -> tuple[str, str]:
    """
    Extract a compact public professional bio from a company-owned page.

    We only use text already present on the page. No inference is performed.
    """
    page_text = extract_page_text(soup)

    person_tokens = name_tokens(person_name)

    if not person_tokens:
        return "", ""

    normalized_page = page_text.casefold()

    if not all(token in normalized_page for token in person_tokens):
        return "", ""

    role_score = role_match_score(
        designation,
        page_text,
    )

    if role_score <= 0:
        return "", ""

    # Look for a sentence-sized region around the person's full name.
    full_name = clean_text(person_name)

    position = normalized_page.find(full_name.casefold())

    if position < 0:
        return "", ""

    start = max(position - 120, 0)
    end = min(position + 700, len(page_text))

    excerpt = clean_text(page_text[start:end])

    if len(excerpt) < 40:
        return "", ""

    return excerpt[:700], "company_owned_page"


def extract_public_location(
    soup: BeautifulSoup,
    person_name: str,
) -> str:
    """
    Extract an explicit location only when a page visibly associates
    a location with the person's name.

    This is intentionally conservative.
    """
    page_text = extract_page_text(soup)

    tokens = name_tokens(person_name)

    if not tokens:
        return ""

    normalized = page_text.casefold()

    if not all(token in normalized for token in tokens):
        return ""

    # We intentionally do not infer a person's location from the
    # company's headquarters or from a generic office list.
    return ""


# ---------------------------------------------------------------------
# Record enrichment
# ---------------------------------------------------------------------


def enrich_record(
    session: requests.Session,
    row: dict[str, str],
) -> dict[str, str]:
    """Enrich one validated Phase 5 record."""
    result = dict(row)

    person_name = clean_text(row.get("person_name", ""))
    designation = clean_text(row.get("designation", ""))
    source_url = normalize_url(row.get("source_url", ""))

    # New Phase 5.1 fields.
    result["company_domain"] = clean_text(row.get("company_domain", "")) or hostname(
        source_url
    )

    # Phase 5 validation remains authoritative.
    phase5_status = clean_text(row.get("validation_status", ""))

    if phase5_status == "VALID":
        result["verification_status"] = "VERIFIED"
    elif phase5_status:
        result["verification_status"] = phase5_status
    else:
        result["verification_status"] = "UNKNOWN"

    result["verification_source"] = source_url
    result["professional_profile_url"] = ""
    result["public_bio_url"] = ""
    result["public_bio_excerpt"] = ""
    result["public_location"] = ""
    result["enrichment_method"] = "company_owned_source"
    result["enrichment_confidence"] = "LOW"
    result["enrichment_status"] = ""
    result["source_fetch_status"] = ""

    if not source_url:
        result["enrichment_status"] = "missing_source_url"
        return result

    response, status = fetch_page(
        session,
        source_url,
    )

    if response is None:
        result["enrichment_status"] = status
        result["source_fetch_status"] = status
        return result

    result["source_fetch_status"] = status

    if status != "ok":
        result["enrichment_status"] = f"additional_evidence_unavailable:{status}"
        result["enrichment_confidence"] = (
            "MEDIUM" if result["verification_status"] == "VERIFIED" else "LOW"
        )
        return result

    final_source_url = normalize_url(response.url) or source_url

    result["verification_source"] = final_source_url

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    page_text = extract_page_text(soup)

    person_present = all(
        token in page_text.casefold() for token in name_tokens(person_name)
    )

    designation_present = (
        designation.casefold() in page_text.casefold() if designation else False
    )

    candidates = find_candidate_profile_links(
        soup,
        person_name,
        designation,
        final_source_url,
    )

    best_profile = choose_best_profile(candidates)

    if best_profile is not None:
        profile_url = normalize_url(str(best_profile["url"]))

        result["professional_profile_url"] = profile_url
        result["public_bio_url"] = profile_url

    bio_excerpt, bio_method = extract_public_bio(
        soup,
        person_name,
        designation,
    )

    if bio_excerpt:
        result["public_bio_excerpt"] = bio_excerpt

    location = extract_public_location(
        soup,
        person_name,
    )

    if location:
        result["public_location"] = location

    if person_present and designation_present:
        result["enrichment_confidence"] = "HIGH"
        result["enrichment_status"] = "person_and_designation_found"
    elif person_present:
        result["enrichment_confidence"] = "MEDIUM"
        result["enrichment_status"] = "person_found_designation_not_confirmed"
    elif best_profile is not None:
        result["enrichment_confidence"] = "MEDIUM"
        result["enrichment_status"] = "profile_link_candidate_found"
    else:
        result["enrichment_status"] = "no_additional_person_evidence_found"

    if bio_excerpt:
        result["enrichment_method"] = f"{result['enrichment_method']};" f"{bio_method}"

    return result


# ---------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------


def load_rows(
    path: Path,
) -> list[dict[str, str]]:
    """Load the Phase 5 final CSV."""
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def write_rows(
    path: Path,
    rows: list[dict[str, str]],
) -> None:
    """Write enriched records."""
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
        return

    fieldnames = list(dict.fromkeys(key for row in rows for key in row))

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------


def print_summary(
    rows: list[dict[str, str]],
) -> None:
    """Print enrichment results."""
    status_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}

    for row in rows:
        status = row.get(
            "enrichment_status",
            "unknown",
        )
        confidence = row.get(
            "enrichment_confidence",
            "unknown",
        )

        status_counts[status] = status_counts.get(status, 0) + 1

        confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1

    print("\nBY ENRICHMENT STATUS")

    for status, count in sorted(
        status_counts.items(),
    ):
        print(f"{status:<40} {count}")

    print("\nBY ENRICHMENT CONFIDENCE")

    confidence_order = (
        "HIGH",
        "MEDIUM",
        "LOW",
    )

    for confidence in confidence_order:
        print(f"{confidence:<10} " f"{confidence_counts.get(confidence, 0)}")

    verified = sum(row.get("verification_status") == "VERIFIED" for row in rows)

    profile_links = sum(bool(row.get("professional_profile_url")) for row in rows)

    bio_records = sum(bool(row.get("public_bio_excerpt")) for row in rows)

    print("\nKEY RESULTS")
    print(f"Verified records       : {verified}")
    print(f"Profile links found    : {profile_links}")
    print(f"Public bio evidence    : {bio_records}")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


def main() -> None:
    print("Cost policy:")
    print("Google Places API : NOT USED")
    print("Google Search API : NOT USED")
    print("Paid API          : NOT USED")
    print("Proxy             : NOT USED")
    print("Scraping service  : NOT USED")

    print("\n============================================================")
    print("PHASE 5.1 - PUBLIC PROFESSIONAL ENRICHMENT")
    print("============================================================")

    rows = load_rows(INPUT_FILE)

    print(f"\nRecords loaded: {len(rows)}")

    if not rows:
        print("No records available.")
        return

    session = create_session()
    enriched: list[dict[str, str]] = []

    for index, row in enumerate(rows, start=1):
        company = clean_text(row.get("company_name", ""))
        person = clean_text(row.get("person_name", ""))
        designation = clean_text(row.get("designation", ""))
        source_url = normalize_url(row.get("source_url", ""))

        print("\n---")
        print(f"RECORD {index}/{len(rows)}")
        print(f"Company     : {company}")
        print(f"Person      : {person}")
        print(f"Designation : {designation}")
        print(f"Source      : {source_url}")

        result = enrich_record(
            session,
            row,
        )

        enriched.append(result)

        print("Status      : " f"{result.get('enrichment_status', '')}")
        print("Verification: " f"{result.get('verification_status', '')}")
        print("Confidence  : " f"{result.get('enrichment_confidence', '')}")

        if result.get("professional_profile_url"):
            print("Profile URL : " f"{result['professional_profile_url']}")

        if index < len(rows):
            time.sleep(REQUEST_DELAY_SECONDS)

    write_rows(
        OUTPUT_FILE,
        enriched,
    )

    print_summary(enriched)

    print("\nFILE")
    print(f"Enriched : {OUTPUT_FILE}")

    print("\n============================================================")
    print("PHASE 5.1 COMPLETE")
    print("============================================================")

    print("\nCompany-owned public enrichment completed.")
    print(
        "Inspect cxo_people_enriched.csv before " "building the next enrichment layer."
    )


if __name__ == "__main__":
    main()
