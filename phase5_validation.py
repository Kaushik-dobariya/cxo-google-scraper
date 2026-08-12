"""
Phase 5 — CXO Data Validation & Enrichment
===========================================

Purpose
-------
Validate the Phase 4 CXO/leadership dataset without paid APIs, proxies,
search APIs, or external enrichment services.

Input:
    output/cxo/cxo_people.csv

Outputs:
    output/cxo/cxo_people_validated.csv
    output/cxo/cxo_people_rejected.csv
    output/cxo/cxo_people_final.csv

Validation philosophy
---------------------
- Preserve source provenance.
- Normalize names and designations.
- Reject obvious extraction contamination.
- Deduplicate records conservatively.
- Score records based on source, extraction method, role quality,
  and field completeness.
- Never invent missing data.
- Do not scrape personal/private information.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

INPUT_FILE = Path("output/cxo/cxo_people.csv")
VALIDATED_FILE = Path("output/cxo/cxo_people_validated.csv")
REJECTED_FILE = Path("output/cxo/cxo_people_rejected.csv")
FINAL_FILE = Path("output/cxo/cxo_people_final.csv")


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BLOCKED_PHRASES = (
    "read bio",
    "read more",
    "view profile",
    "view bio",
    "learn more",
    "know more",
    "click here",
    "adaptability starts here",
    "starts here",
)

ROLE_NOISE = (
    "view profile",
    "view bio",
    "read bio",
    "read more",
    "learn more",
    "know more",
)

CXO_ROLE_PATTERNS = (
    r"\bchief executive officer\b",
    r"\bchief operating officer\b",
    r"\bchief financial officer\b",
    r"\bchief technology officer\b",
    r"\bchief information officer\b",
    r"\bchief marketing officer\b",
    r"\bchief people officer\b",
    r"\bchief human resources officer\b",
    r"\bchief strategy officer\b",
    r"\bchief legal officer\b",
    r"\bchief risk officer\b",
    r"\bchief data officer\b",
    r"\bchief product officer\b",
    r"\bchief commercial officer\b",
    r"\bchief customer officer\b",
    r"\bchief security officer\b",
    r"\bchief procurement officer\b",
    r"\bchief revenue officer\b",
    r"\bchief administrative officer\b",
    r"\bchief digital officer\b",
    r"\bchief sustainability officer\b",
    r"\bchief investment officer\b",
    r"\bchief information security officer\b",
    r"\bmanaging director\b",
    r"\bpresident\b",
    r"\bchief\b",
)

BOARD_ROLE_PATTERNS = (
    r"\bchairman\b",
    r"\bchairperson\b",
    r"\bvice chairman\b",
    r"\bindependent director\b",
    r"\bnon[- ]executive director\b",
    r"\bexecutive chairman\b",
    r"\bboard director\b",
)

EXECUTIVE_ROLE_PATTERNS = (
    r"\bexecutive director\b",
    r"\bgroup director\b",
    r"\bexecutive vice president\b",
    r"\bsenior vice president\b",
    r"\bvice president\b",
)

SOURCE_METHOD_BONUS = {
    "sibling_pair": 20,
    "semantic_card": 20,
    "tcs_executive_section": 20,
    "profile_link_card": 20,
    "structural_pair": 15,
}

LEADERSHIP_TYPE_NORMALIZATION = {
    "cxo": "CXO",
    "board": "Board",
    "executive leadership": "Executive Leadership",
    "executive": "Executive Leadership",
}


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------


def clean_text(value: object) -> str:
    """Normalize whitespace and return a safe string."""
    text = "" if value is None else str(value)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_name(value: object) -> str:
    """Normalize spacing and punctuation around a person's name."""
    text = clean_text(value)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.'’])", r"\1", text)
    return text.strip(" -–—|")


def normalize_designation(value: object) -> str:
    """Clean obvious UI noise while preserving the actual designation."""
    text = clean_text(value)

    for phrase in ROLE_NOISE:
        text = re.sub(
            rf"\s*{re.escape(phrase)}\s*",
            " ",
            text,
            flags=re.IGNORECASE,
        )

    text = re.sub(r"\s+", " ", text)
    return text.strip(" -–—|,;")


def normalize_company(value: object) -> str:
    return clean_text(value)


def normalize_url(value: object) -> str:
    """Return a normalized HTTP(S) URL."""
    value = clean_text(value)

    if not value:
        return ""

    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    return value.rstrip("/")


def normalize_leadership_type(
    value: object,
    designation: str,
) -> str:
    """
    Normalize leadership type using a designation-first hierarchy.

    Priority:
        1. Explicit board/governance designation
        2. Explicit CXO designation
        3. Executive leadership designation
        4. Phase 4 supplied classification
        5. Unknown

    Important:
        "President" alone is Executive Leadership.
        "President + COO/CFO/CIO/etc." becomes CXO because the chief role
        is the stronger operational designation.
    """
    designation_text = normalize_designation(designation)
    lowered = designation_text.casefold()
    supplied = clean_text(value).casefold()

    # -------------------------------------------------------------
    # 1. Explicit board / governance roles.
    # -------------------------------------------------------------
    board_patterns = (
        r"\bindependent director\b",
        r"\blead independent director\b",
        r"\bnon[- ]executive director\b",
        r"\bnonexecutive director\b",
        r"\bchairman\b",
        r"\bchairperson\b",
        r"\bvice chairman\b",
        r"\bvice chairperson\b",
        r"\bexecutive chairman\b",
        r"\bnon[- ]executive chairman\b",
        r"\bnonexecutive chairman\b",
    )

    if any(re.search(pattern, lowered) for pattern in board_patterns):
        return "Board"

    if re.fullmatch(
        r"\s*(?:lead\s+)?director\s*",
        lowered,
    ):
        return "Board"

    # -------------------------------------------------------------
    # 2. Explicit CXO / operational chief roles.
    # -------------------------------------------------------------
    cxo_patterns = (
        r"\bchief\s+executive\s+officer\b",
        r"\bchief\s+operating\s+officer\b",
        r"\bchief\s+financial\s+officer\b",
        r"\bchief\s+technology\s+officer\b",
        r"\bchief\s+information\s+officer\b",
        r"\bchief\s+marketing\s+officer\b",
        r"\bchief\s+people\s+officer\b",
        r"\bchief\s+human\s+resources\s+officer\b",
        r"\bchief\s+strategy\s+officer\b",
        r"\bchief\s+strategy\s+and\s+risk\s+officer\b",
        r"\bchief\s+legal\s+officer\b",
        r"\bchief\s+risk\s+officer\b",
        r"\bchief\s+data\s+officer\b",
        r"\bchief\s+product\s+officer\b",
        r"\bchief\s+commercial\s+officer\b",
        r"\bchief\s+customer\s+officer\b",
        r"\bchief\s+security\s+officer\b",
        r"\bchief\s+procurement\s+officer\b",
        r"\bchief\s+revenue\s+officer\b",
        r"\bchief\s+administrative\s+officer\b",
        r"\bchief\s+digital\s+officer\b",
        r"\bchief\s+sustainability\s+officer\b",
        r"\bchief\s+investment\s+officer\b",
        r"\bchief\s+information\s+security\s+officer\b",
        r"\bmanaging\s+director\b",
    )

    if any(re.search(pattern, lowered) for pattern in cxo_patterns):
        return "CXO"

    # -------------------------------------------------------------
    # 3. Executive leadership roles.
    # -------------------------------------------------------------
    executive_patterns = (
        r"\bpresident\b",
        r"\bexecutive director\b",
        r"\bgroup director\b",
        r"\bexecutive vice president\b",
        r"\bsenior vice president\b",
        r"\bvice president\b",
        r"\bgeneral counsel\b",
        r"\bcompany secretary\b",
    )

    if any(re.search(pattern, lowered) for pattern in executive_patterns):
        return "Executive Leadership"

    # -------------------------------------------------------------
    # 4. Preserve an already valid Phase 4 classification.
    # -------------------------------------------------------------
    if supplied in LEADERSHIP_TYPE_NORMALIZATION:
        return LEADERSHIP_TYPE_NORMALIZATION[supplied]

    return "Unknown"


def looks_like_person_name(name: str) -> bool:
    """Reject obvious UI labels and sentence-like strings."""
    name = normalize_name(name)

    if not name:
        return False

    lowered = name.casefold()

    if any(phrase in lowered for phrase in BLOCKED_PHRASES):
        return False

    if len(name) < 4 or len(name) > 100:
        return False

    words = name.split()

    if len(words) < 2 or len(words) > 7:
        return False

    if sum(char.isalpha() for char in name) < 3:
        return False

    # Names should not contain URL-like or HTML-like content.
    if any(token in lowered for token in ("http://", "https://", "<", ">")):
        return False

    # Reject obvious sentence fragments.
    sentence_words = {
        "the",
        "starts",
        "here",
        "about",
        "leadership",
        "profile",
        "read",
        "more",
        "view",
        "learn",
        "contact",
        "careers",
    }

    return sum(word.casefold() in sentence_words for word in words) < 2


def looks_like_clean_designation(designation: str) -> bool:
    """Validate that a designation looks like a professional role."""
    designation = normalize_designation(designation)

    if not designation:
        return False

    lowered = designation.casefold()

    if len(designation) > 180:
        return False

    if any(phrase in lowered for phrase in BLOCKED_PHRASES):
        return False

    if "http://" in lowered or "https://" in lowered:
        return False

    # A designation should contain at least one recognizable leadership
    # term. This prevents generic page/card text from passing validation.
    role_terms = (
        "chief",
        "officer",
        "executive",
        "president",
        "director",
        "chairman",
        "chairperson",
        "managing director",
        "vice president",
        "founder",
        "co-founder",
        "secretary",
        "general counsel",
    )

    return any(term in lowered for term in role_terms)


def contains_other_person_name(
    name: str,
    designation: str,
    all_names: set[str],
) -> bool:
    """Reject composite designations containing another extracted name."""
    designation_lower = designation.casefold()

    current = normalize_name(name).casefold()

    for other in all_names:
        normalized_other = normalize_name(other).casefold()

        if not normalized_other or normalized_other == current:
            continue

        if len(normalized_other) < 5:
            continue

        if normalized_other in designation_lower:
            return True

    return False


def source_quality(row: dict[str, str]) -> int:
    """Score source provenance without pretending it is factual certainty."""
    score = 0

    method = clean_text(row.get("extraction_method", "")).casefold()

    score += SOURCE_METHOD_BONUS.get(method, 10)

    source_url = normalize_url(row.get("source_url", ""))

    if source_url:
        score += 15

        hostname = urlparse(source_url).hostname or ""

        if hostname:
            score += 10

    return score


def role_quality(
    designation: str,
    leadership_type: str,
) -> int:
    """Score professional-role quality."""
    score = 0
    lowered = designation.casefold()

    if leadership_type == "CXO":
        score += 25
    elif leadership_type == "Board" or leadership_type == "Executive Leadership":
        score += 20

    if "chief" in lowered:
        score += 10

    if "officer" in lowered:
        score += 10

    if "managing director" in lowered:
        score += 10

    return min(score, 50)


def calculate_quality_score(
    row: dict[str, str],
) -> int:
    """Calculate a transparent 0–100 validation score."""
    name = normalize_name(row.get("person_name", ""))
    designation = normalize_designation(row.get("designation", ""))
    leadership_type = normalize_leadership_type(
        row.get("leadership_type", ""),
        designation,
    )

    score = source_quality(row)
    score += role_quality(designation, leadership_type)

    if looks_like_person_name(name):
        score += 10

    if looks_like_clean_designation(designation):
        score += 10

    if normalize_company(row.get("company_name", "")):
        score += 5

    return min(score, 100)


def validation_status(
    row: dict[str, str],
    all_names: set[str],
) -> tuple[str, str]:
    """Return VALID/REJECTED plus a human-readable reason."""
    name = normalize_name(row.get("person_name", ""))
    designation = normalize_designation(row.get("designation", ""))
    source_url = normalize_url(row.get("source_url", ""))

    if not looks_like_person_name(name):
        return "REJECTED", "invalid_person_name"

    if not looks_like_clean_designation(designation):
        return "REJECTED", "invalid_designation"

    if contains_other_person_name(
        name,
        designation,
        all_names,
    ):
        return "REJECTED", "designation_contains_other_person"

    if not source_url:
        return "REJECTED", "missing_source_url"

    if not normalize_company(row.get("company_name", "")):
        return "REJECTED", "missing_company"

    return "VALID", "passed_validation"


def dedupe_key(row: dict[str, str]) -> tuple[str, str, str]:
    """Conservative identity key."""
    company = normalize_company(row.get("company_name", "")).casefold()

    name = normalize_name(row.get("person_name", "")).casefold()

    designation = normalize_designation(row.get("designation", "")).casefold()

    return company, name, designation


# ---------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------


def load_rows(path: Path) -> list[dict[str, str]]:
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
    fieldnames: list[str],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
# Validation pipeline
# ---------------------------------------------------------------------


def validate_rows(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """
    Validate and normalize Phase 4 records.

    No external requests are made here.
    """
    all_names = {
        normalize_name(row.get("person_name", ""))
        for row in rows
        if normalize_name(row.get("person_name", ""))
    }

    validated: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []

    for original in rows:
        row = dict(original)

        row["company_name"] = normalize_company(row.get("company_name", ""))
        row["person_name"] = normalize_name(row.get("person_name", ""))
        row["designation"] = normalize_designation(row.get("designation", ""))
        row["leadership_type"] = normalize_leadership_type(
            row.get("leadership_type", ""),
            row["designation"],
        )
        row["source_url"] = normalize_url(row.get("source_url", ""))

        status, reason = validation_status(
            row,
            all_names,
        )

        row["validation_status"] = status
        row["validation_reason"] = reason
        row["quality_score"] = str(calculate_quality_score(row))

        if status == "VALID":
            validated.append(row)
        else:
            rejected.append(row)

    return validated, rejected


def deduplicate_rows(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], int]:
    """
    Keep the highest-quality record for each exact
    company + person + designation identity.
    """
    best: dict[tuple[str, str, str], dict[str, str]] = {}

    for row in rows:
        key = dedupe_key(row)

        current_score = int(row.get("quality_score", "0") or "0")

        previous = best.get(key)

        if previous is None:
            best[key] = row
            continue

        previous_score = int(previous.get("quality_score", "0") or "0")

        if current_score > previous_score:
            best[key] = row

    removed = len(rows) - len(best)

    return list(best.values()), removed


def prepare_final_rows(
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Add final pipeline metadata."""
    output: list[dict[str, str]] = []

    for row in rows:
        item = dict(row)
        item["final_status"] = "READY"
        output.append(item)

    return output


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------


def print_company_summary(
    rows: list[dict[str, str]],
) -> None:
    counts = Counter(row.get("company_name", "") for row in rows)

    print("\nBY COMPANY")

    for company, count in sorted(
        counts.items(),
        key=lambda item: item[0].casefold(),
    ):
        print(f"{company:<35} {count}")


def print_type_summary(
    rows: list[dict[str, str]],
) -> None:
    counts = Counter(row.get("leadership_type", "Unknown") for row in rows)

    print("\nBY LEADERSHIP TYPE")

    for leadership_type, count in sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(f"{leadership_type:<25} {count}")


def main() -> None:
    print("Cost policy:")
    print("Google Places API : NOT USED")
    print("Google Search API : NOT USED")
    print("Paid API          : NOT USED")
    print("Proxy             : NOT USED")
    print("Scraping service  : NOT USED")

    print("\n============================================================")
    print("PHASE 5 - CXO DATA VALIDATION & ENRICHMENT")
    print("============================================================")

    rows = load_rows(INPUT_FILE)

    print(f"\nRecords loaded: {len(rows)}")

    if not rows:
        print("No records available.")
        return

    validated, rejected = validate_rows(rows)

    print(f"Validated before deduplication : {len(validated)}")
    print(f"Rejected                        : {len(rejected)}")

    final_rows, duplicates_removed = deduplicate_rows(validated)

    final_rows = prepare_final_rows(final_rows)

    print(f"Duplicates removed              : {duplicates_removed}")
    print(f"Final records                   : {len(final_rows)}")

    write_fields = list(
        dict.fromkeys(
            [
                *rows[0].keys(),
                "validation_status",
                "validation_reason",
                "quality_score",
                "final_status",
            ]
        )
    )

    write_rows(
        VALIDATED_FILE,
        validated,
        write_fields,
    )

    write_rows(
        REJECTED_FILE,
        rejected,
        write_fields,
    )

    write_rows(
        FINAL_FILE,
        final_rows,
        write_fields,
    )

    print_company_summary(final_rows)
    print_type_summary(final_rows)

    print("\nFILES")
    print(f"Validated : {VALIDATED_FILE}")
    print(f"Rejected  : {REJECTED_FILE}")
    print(f"Final     : {FINAL_FILE}")

    print("\n============================================================")
    print("PHASE 5 COMPLETE")
    print("============================================================")
    print("\nPhase 5 validation completed.")
    print("Inspect cxo_people_final.csv before proceeding.")


if __name__ == "__main__":
    main()
