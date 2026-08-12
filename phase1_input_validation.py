"""
Phase 1 — Website Input & Validation
====================================

Input:
    input/companies.csv

Expected input columns:
    company_name,website

Output:
    output/companies.csv

Purpose
-------
Validate and normalize the initial company list before any website
discovery or contact/CXO extraction begins.

Cost policy:
    Google Places API : NOT USED
    Google Search API : NOT USED
    Paid API          : NOT USED
    Proxy             : NOT USED
    Scraping service  : NOT USED
"""

from __future__ import annotations

import csv
import re
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests

INPUT_FILE = Path("input/companies.csv")
OUTPUT_FILE = Path("output/companies.csv")

REQUEST_TIMEOUT = 20
REQUEST_DELAY_SECONDS = 0.5

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0 Safari/537.36"
)

OUTPUT_FIELDS = [
    "company_name",
    "input_website",
    "website",
    "company_domain",
    "final_url",
    "status_code",
    "reachable",
    "page_title",
    "validation_status",
]


def clean_text(value: object) -> str:
    """Normalize whitespace."""
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).replace("\xa0", " "),
    ).strip()


def normalize_url(value: object) -> str:
    """Normalize an HTTP(S) URL."""
    value = clean_text(value)

    if not value:
        return ""

    if not re.match(
        r"^https?://",
        value,
        flags=re.IGNORECASE,
    ):
        value = f"https://{value}"

    parsed = urlparse(value)

    if parsed.scheme.casefold() not in {
        "http",
        "https",
    }:
        return ""

    if not parsed.netloc:
        return ""

    return urlunparse(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            parsed.path or "/",
            "",
            parsed.query,
            "",
        )
    )


def normalize_domain(value: str) -> str:
    """Extract a normalized hostname."""
    parsed = urlparse(value)

    host = parsed.hostname or ""

    return host.casefold().removeprefix("www.")


def is_valid_company_name(value: str) -> bool:
    """Basic company-name validation."""
    value = clean_text(value)

    if len(value) < 2 or len(value) > 200:
        return False

    return bool(
        re.search(
            r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]",
            value,
        )
    )


def create_session() -> requests.Session:
    """Create a normal HTTP session."""
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml," "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.8",
        }
    )

    return session


def load_input() -> list[dict[str, str]]:
    """Load input companies and validate the required header."""
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        return []

    try:
        with INPUT_FILE.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            reader = csv.DictReader(handle)

            if not reader.fieldnames:
                print("[ERROR] CSV has no header.")
                return []

            header_map = {
                field.casefold(): field for field in reader.fieldnames if field
            }

            company_column = header_map.get("company_name")

            website_column = (
                header_map.get("website")
                or header_map.get("website_url")
                or header_map.get("url")
            )

            if not company_column or not website_column:
                print("[ERROR] CSV must contain " "company_name and website columns.")
                return []

            companies: list[dict[str, str]] = []

            for row in reader:
                company_name = clean_text(row.get(company_column, ""))

                website = normalize_url(row.get(website_column, ""))

                if not company_name and not website:
                    continue

                companies.append(
                    {
                        "company_name": company_name,
                        "website": website,
                    }
                )

            return companies

    except OSError as error:
        print(f"[ERROR] Could not read input CSV: {error}")
        return []


def deduplicate_input(
    companies: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Remove duplicate company/domain entries while preserving order."""
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for company in companies:
        name = clean_text(company.get("company_name", "")).casefold()

        website = normalize_url(company.get("website", ""))

        domain = normalize_domain(website)

        key = (
            name,
            domain,
        )

        if key in seen:
            continue

        seen.add(key)

        result.append(
            {
                "company_name": clean_text(company.get("company_name", "")),
                "website": website,
            }
        )

    return result


def fetch_company(
    session: requests.Session,
    company: dict[str, str],
) -> dict[str, str]:
    """Validate one company website."""
    company_name = clean_text(company.get("company_name", ""))

    input_url = normalize_url(company.get("website", ""))

    result = {
        "company_name": company_name,
        "input_website": input_url,
        "website": input_url,
        "company_domain": normalize_domain(input_url),
        "final_url": "",
        "status_code": "",
        "reachable": "NO",
        "page_title": "",
        "validation_status": "",
    }

    if not is_valid_company_name(company_name):
        result["validation_status"] = "INVALID_COMPANY_NAME"
        return result

    if not input_url:
        result["validation_status"] = "INVALID_WEBSITE"
        return result

    try:
        response = session.get(
            input_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException as error:
        result["validation_status"] = f"REQUEST_ERROR:{type(error).__name__}"
        return result

    result["status_code"] = str(response.status_code)

    result["final_url"] = normalize_url(response.url)

    if result["final_url"]:
        result["company_domain"] = normalize_domain(result["final_url"])

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).casefold()

    if response.status_code < 400:
        result["reachable"] = "YES"

        if "html" in content_type:
            title_match = re.search(
                r"<title[^>]*>(.*?)</title>",
                response.text,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if title_match:
                result["page_title"] = clean_text(
                    re.sub(
                        r"<[^>]+>",
                        " ",
                        title_match.group(1),
                    )
                )

        result["validation_status"] = "VALIDATED"

    elif response.status_code == 403:
        result["validation_status"] = "BLOCKED_403"

    elif response.status_code == 401:
        result["validation_status"] = "BLOCKED_401"

    elif response.status_code == 429:
        result["validation_status"] = "RATE_LIMITED_429"

    else:
        result["validation_status"] = f"HTTP_{response.status_code}"

    return result


def save_output(
    rows: list[dict[str, str]],
) -> None:
    """Save validated company records."""
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=OUTPUT_FIELDS,
        )

        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    print()
    print("=" * 70)
    print("CXO GOOGLE SCRAPER")
    print("PHASE 1 - WEBSITE INPUT & VALIDATION")
    print("=" * 70)

    print()
    print("Cost policy:")
    print("Google Places API : NOT USED")
    print("Google Search API : NOT USED")
    print("Paid API          : NOT USED")
    print("Proxy             : NOT USED")
    print("Scraping service  : NOT USED")

    companies = load_input()

    if not companies:
        print()
        print("No input companies available.")
        print(f"File: {INPUT_FILE}")
        return

    companies = deduplicate_input(companies)

    print()
    print(f"Companies loaded           : {len(companies)}")

    session = create_session()
    results: list[dict[str, str]] = []

    for index, company in enumerate(
        companies,
        start=1,
    ):
        print()
        print("-" * 70)
        print(f"PROCESSING {index}/{len(companies)}")
        print(f"Company : {company['company_name']}")
        print(f"Website : {company['website']}")

        result = fetch_company(
            session,
            company,
        )

        results.append(result)

        print(f"Status  : " f"{result['status_code'] or 'N/A'}")
        print(f"Reachable : " f"{result['reachable']}")
        print(f"Domain : " f"{result['company_domain']}")
        print(f"Title  : " f"{result['page_title'] or 'N/A'}")
        print(f"Validation : " f"{result['validation_status']}")

        if index < len(companies):
            time.sleep(REQUEST_DELAY_SECONDS)

    save_output(results)

    reachable = sum(row["reachable"] == "YES" for row in results)

    not_reachable = len(results) - reachable

    print()
    print("=" * 70)
    print("PHASE 1 COMPLETE")
    print("=" * 70)

    print(f"Total companies : {len(results)}")
    print(f"Reachable       : {reachable}")
    print(f"Not reachable   : {not_reachable}")
    print()
    print(f"File: {OUTPUT_FILE}")
    print(f"Records: {len(results)}")
    print()
    print("Website input and validation completed.")
    print()
    print("Next phase:")
    print("Phase 2 - Website Discovery & Crawling")


if __name__ == "__main__":
    main()
