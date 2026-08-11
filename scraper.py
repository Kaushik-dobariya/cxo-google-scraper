"""
CXO GOOGLE SCRAPER
==================

Phase 1.1
---------
Free company discovery from public web search results.

IMPORTANT:
- No Google Places API
- No paid API
- No proxy
- No scraping service
- No CAPTCHA bypass

Input:
    input/search.csv

Output:
    output/companies.csv
"""

from __future__ import annotations

import csv
import time
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

import config


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update(
    config.HEADERS
)


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(value: str) -> str:
    """Clean unnecessary whitespace."""

    if not value:
        return ""

    return " ".join(
        value.split()
    ).strip()


# ============================================================
# URL HELPERS
# ============================================================

def get_domain(url: str) -> str:
    """Return clean domain name from URL."""

    try:

        parsed = urlparse(url)

        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:

        return ""


def is_valid_url(url: str) -> bool:
    """Check whether URL is HTTP/HTTPS."""

    try:

        parsed = urlparse(url)

        return (
            parsed.scheme in (
                "http",
                "https",
            )
            and bool(parsed.netloc)
        )

    except Exception:

        return False


def is_excluded_domain(url: str) -> bool:
    """
    Exclude search engines, social media,
    directories, etc.
    """

    domain = get_domain(url)

    if not domain:
        return True

    for excluded in config.EXCLUDED_DOMAINS:

        if (
            domain == excluded
            or domain.endswith(
                "." + excluded
            )
        ):
            return True

    return False


# ============================================================
# SEARCH RESULT URL
# ============================================================

def extract_real_url(href: str) -> str:
    """
    Extract actual destination URL.

    DuckDuckGo may use redirect URLs containing
    the 'uddg' parameter.
    """

    if not href:
        return ""

    href = href.strip()

    # --------------------------------------------------------
    # Absolute URL
    # --------------------------------------------------------

    if href.startswith(
        (
            "http://",
            "https://",
        )
    ):

        parsed = urlparse(href)

        query = parse_qs(
            parsed.query
        )

        if "uddg" in query:

            return unquote(
                query["uddg"][0]
            )

        return href

    # --------------------------------------------------------
    # Protocol-relative URL
    # --------------------------------------------------------

    if href.startswith("//"):

        href = "https:" + href

    # --------------------------------------------------------
    # Relative URL
    # --------------------------------------------------------

    elif href.startswith("/"):

        href = (
            "https://html.duckduckgo.com"
            + href
        )

    parsed = urlparse(href)

    query = parse_qs(
        parsed.query
    )

    if "uddg" in query:

        return unquote(
            query["uddg"][0]
        )

    return href


# ============================================================
# SEARCH RESPONSE DIAGNOSTICS
# ============================================================

def diagnose_response(
    response: requests.Response,
) -> None:
    """
    Print useful diagnostics when the search engine
    doesn't return the expected result structure.
    """

    print()
    print(
        "HTTP status :",
        response.status_code,
    )

    print(
        "Final URL   :",
        response.url,
    )

    print(
        "Content-Type:",
        response.headers.get(
            "Content-Type",
            "",
        ),
    )

    print(
        "Response size:",
        len(response.text),
        "characters",
    )

    # --------------------------------------------------------
    # Look for common indicators.
    # --------------------------------------------------------

    lower_html = response.text.lower()

    indicators = [
        "captcha",
        "unusual traffic",
        "robot",
        "blocked",
        "forbidden",
        "access denied",
        "challenge",
    ]

    found = [
        item
        for item in indicators
        if item in lower_html
    ]

    if found:

        print(
            "Possible response indicators:",
            ", ".join(found),
        )


# ============================================================
# DUCKDUCKGO SEARCH
# ============================================================

def search_web(
    query: str,
    max_results: int,
) -> list[dict]:
    """
    Search DuckDuckGo public HTML.

    We use the current result-link selector:

        .result__a
    """

    print()
    print("-" * 70)
    print(
        f"SEARCHING: {query}"
    )
    print("-" * 70)

    search_url = (
        "https://html.duckduckgo.com/html/"
    )

    params = {
        "q": query,
        "kl": "in-en",
    }

    # --------------------------------------------------------
    # Browser-like request headers.
    # --------------------------------------------------------

    headers = {
        "Referer":
            "https://html.duckduckgo.com/",
        "Sec-Fetch-Dest":
            "document",
        "Sec-Fetch-Mode":
            "navigate",
        "Sec-Fetch-Site":
            "same-origin",
        "Sec-Fetch-User":
            "?1",
        "Upgrade-Insecure-Requests":
            "1",
    }

    try:

        response = session.get(
            search_url,
            params=params,
            headers=headers,
            timeout=config.REQUEST_TIMEOUT,
        )

        response.raise_for_status()

    except requests.RequestException as error:

        print(
            "[ERROR] Search request failed:"
        )

        print(error)

        return []

    # --------------------------------------------------------
    # Diagnostics
    # --------------------------------------------------------

    diagnose_response(
        response
    )

    # --------------------------------------------------------
    # Parse HTML.
    # --------------------------------------------------------

    soup = BeautifulSoup(
        response.text,
        "lxml",
    )

    # --------------------------------------------------------
    # Current DDG result structure.
    #
    # Result:
    #   .result
    #
    # Link:
    #   .result__a
    #
    # Snippet:
    #   .result__snippet
    # --------------------------------------------------------

    result_blocks = soup.select(
        ".result"
    )

    print(
        "Result blocks found:",
        len(result_blocks),
    )

    results = []

    for block in result_blocks:

        # ----------------------------------------------------
        # Find result link.
        # ----------------------------------------------------

        link_element = block.select_one(
            ".result__a"
        )

        if not link_element:

            continue

        href = link_element.get(
            "href",
            "",
        )

        website = extract_real_url(
            href
        )

        if not is_valid_url(
            website
        ):

            continue

        if is_excluded_domain(
            website
        ):

            continue

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        title = clean_text(
            link_element.get_text(
                " ",
                strip=True,
            )
        )

        # ----------------------------------------------------
        # Snippet
        # ----------------------------------------------------

        snippet_element = (
            block.select_one(
                ".result__snippet"
            )
        )

        description = ""

        if snippet_element:

            description = clean_text(
                snippet_element.get_text(
                    " ",
                    strip=True,
                )
            )

        results.append(
            {
                "title": title,
                "website": website,
                "description": description,
            }
        )

        if len(results) >= max_results:

            break

    print(
        "Usable results:",
        len(results),
    )

    return results


# ============================================================
# READ SEARCH CSV
# ============================================================

def load_search_queries() -> list[str]:
    """Read search.csv and build search queries."""

    search_file = (
        config.SEARCH_FILE
    )

    if not search_file.exists():

        print()
        print(
            "[ERROR] Search file not found:"
        )

        print(
            search_file
        )

        return []

    queries = []

    with open(
        search_file,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(
            file
        )

        if not reader.fieldnames:

            print(
                "[ERROR] search.csv has no header."
            )

            return []

        required_columns = {
            "keyword",
            "location",
        }

        missing = (
            required_columns
            - set(reader.fieldnames)
        )

        if missing:

            print(
                "[ERROR] Missing columns:"
            )

            print(
                ", ".join(missing)
            )

            return []

        for row in reader:

            keyword = clean_text(
                row.get(
                    "keyword",
                    "",
                )
            )

            location = clean_text(
                row.get(
                    "location",
                    "",
                )
            )

            if not keyword:

                continue

            if location:

                query = (
                    f"{keyword} "
                    f"in {location}"
                )

            else:

                query = keyword

            queries.append(
                query
            )

    return queries[
        :config.MAX_SEARCH_QUERIES
    ]


# ============================================================
# DUPLICATE REMOVAL
# ============================================================

def remove_duplicates(
    results: list[dict],
) -> list[dict]:
    """Remove duplicate websites by domain."""

    unique = []

    seen_domains = set()

    for result in results:

        website = result.get(
            "website",
            "",
        )

        domain = get_domain(
            website
        )

        if not domain:

            continue

        if domain in seen_domains:

            continue

        seen_domains.add(
            domain
        )

        unique.append(
            result
        )

    return unique


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(
    results: list[dict],
) -> None:
    """Save results to companies.csv."""

    config.OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        config.COMPANIES_FILE
    )

    fieldnames = [
        "company_name",
        "website",
        "description",
    ]

    with open(
        output_file,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for result in results:

            writer.writerow(
                {
                    "company_name":
                        result.get(
                            "title",
                            "",
                        ),
                    "website":
                        result.get(
                            "website",
                            "",
                        ),
                    "description":
                        result.get(
                            "description",
                            "",
                        ),
                }
            )

    print()
    print("=" * 70)
    print("OUTPUT CREATED")
    print("=" * 70)

    print(
        "File:",
        output_file,
    )

    print(
        "Records:",
        len(results),
    )


# ============================================================
# DISPLAY RESULTS
# ============================================================

def display_results(
    results: list[dict],
) -> None:

    print()
    print("=" * 70)
    print("DISCOVERED COMPANIES")
    print("=" * 70)

    if not results:

        print(
            "No companies discovered."
        )

        return

    for index, result in enumerate(
        results,
        start=1,
    ):

        print()
        print(
            f"{index}. "
            f"{result.get('title', '')}"
        )

        print(
            f"   Website: "
            f"{result.get('website', '')}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("CXO GOOGLE SCRAPER")
    print("PHASE 1.1 - COMPANY DISCOVERY")
    print("=" * 70)

    print()
    print(
        "Cost policy:"
    )

    print(
        "  Google Places API : NOT USED"
    )

    print(
        "  Paid API          : NOT USED"
    )

    print(
        "  Proxy             : NOT USED"
    )

    print(
        "  Scraping service  : NOT USED"
    )

    # --------------------------------------------------------
    # Load search queries.
    # --------------------------------------------------------

    queries = load_search_queries()

    if not queries:

        print()
        print(
            "[ERROR] No search queries found."
        )

        return

    print()
    print(
        f"Search queries loaded: "
        f"{len(queries)}"
    )

    # --------------------------------------------------------
    # Search.
    # --------------------------------------------------------

    all_results = []

    for index, query in enumerate(
        queries,
        start=1,
    ):

        print()
        print(
            f"QUERY "
            f"{index}/"
            f"{len(queries)}"
        )

        results = search_web(
            query,
            config.MAX_RESULTS_PER_QUERY,
        )

        all_results.extend(
            results
        )

        if index < len(queries):

            time.sleep(
                config.REQUEST_DELAY
            )

    # --------------------------------------------------------
    # Remove duplicates.
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("REMOVING DUPLICATES")
    print("=" * 70)

    before = len(
        all_results
    )

    all_results = remove_duplicates(
        all_results
    )

    after = len(
        all_results
    )

    print(
        f"Before: {before}"
    )

    print(
        f"After : {after}"
    )

    # --------------------------------------------------------
    # Display.
    # --------------------------------------------------------

    display_results(
        all_results
    )

    # --------------------------------------------------------
    # Save.
    # --------------------------------------------------------

    save_results(
        all_results
    )

    print()
    print("=" * 70)
    print("PHASE 1.1 FINISHED")
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
