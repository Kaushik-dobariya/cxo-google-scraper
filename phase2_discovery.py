"""
CXO GOOGLE SCRAPER
==================

PHASE 2.7
---------
Precision CXO-Focused Website Discovery

Purpose
-------
Discover company-owned pages relevant to:
    - leadership
    - management
    - executives
    - founders
    - board/directors
    - team/people
    - about/company profile
    - contact

Discovery sources
-----------------
1. Homepage navigation links
2. sitemap.xml
3. robots.txt sitemap declarations
4. A bounded set of common company-page paths

No paid APIs, Google Search API, proxies, or scraping services are used.
"""

from __future__ import annotations

import csv
import re
import time
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config

# ============================================================
# HTTP
# ============================================================

session = requests.Session()
session.headers.update(config.HEADERS)


# ============================================================
# TEXT
# ============================================================


def clean_text(value: str) -> str:
    """Normalize whitespace."""
    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


# ============================================================
# DOMAIN
# ============================================================


def extract_domain(url: str) -> str:
    """Return normalized hostname."""
    if not url:
        return ""

    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return ""

    return (parsed.hostname or "").lower().removeprefix("www.")


# ============================================================
# URL NORMALIZATION
# ============================================================


def normalize_url(
    url: str,
    base_url: str = "",
) -> str:
    """Convert URL into normalized absolute URL."""
    if not url:
        return ""

    url = clean_text(url)

    if not url:
        return ""

    if base_url:
        url = urljoin(
            base_url,
            url,
        )

    url, _fragment = urldefrag(url)

    if len(url) > config.MAX_URL_LENGTH:
        return ""

    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return ""

    if parsed.scheme not in config.ALLOWED_SCHEMES or not parsed.netloc:
        return ""

    hostname = (parsed.hostname or "").lower().removeprefix("www.")

    if not hostname:
        return ""

    normalized = f"{parsed.scheme}://{hostname}"

    try:
        port = parsed.port
    except ValueError:
        return ""

    if port:
        normalized += f":{port}"

    normalized += parsed.path or "/"

    if parsed.query:
        normalized += f"?{parsed.query}"

    return normalized


# ============================================================
# URL VALIDATION
# ============================================================


def is_valid_url(url: str) -> bool:
    """Check HTTP/HTTPS URL."""
    if not url:
        return False

    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return False

    return parsed.scheme in config.ALLOWED_SCHEMES and bool(parsed.netloc)


# ============================================================
# SAME DOMAIN
# ============================================================


def is_same_domain(
    url: str,
    base_url: str,
) -> bool:
    """Check company domain."""
    return extract_domain(url) == extract_domain(base_url)


# ============================================================
# PATH SEGMENTS
# ============================================================


def get_path_segments(url: str) -> list[str]:
    """Return normalized path segments."""
    path = urlparse(url).path.lower()

    segments: list[str] = []

    for segment in path.split("/"):
        segment = segment.strip()

        if not segment:
            continue

        segment = re.sub(
            r"\.(html?|php|aspx?)$",
            "",
            segment,
        )

        if segment:
            segments.append(segment)

    return segments


# ============================================================
# EXCLUDED PATH
# ============================================================


def is_excluded_path(url: str) -> bool:
    """Reject irrelevant corporate content."""
    segments = get_path_segments(url)

    for segment in segments:
        if segment in config.EXCLUDED_PATH_SEGMENTS:
            return True

        for keyword in config.EXCLUDED_SEGMENT_KEYWORDS:
            if keyword in segment:
                return True

    return False


# ============================================================
# HOMEPAGE
# ============================================================


def is_homepage(
    url: str,
    company_homepage: str,
) -> bool:
    """Return True when URL is company homepage."""
    if extract_domain(url) != extract_domain(company_homepage):
        return False

    return urlparse(url).path.strip("/") == ""


# ============================================================
# TERMINAL SEGMENT
# ============================================================


def get_terminal_segment(url: str) -> str:
    """Return the final meaningful URL segment."""
    segments = get_path_segments(url)

    if not segments:
        return ""

    return segments[-1]


# ============================================================
# PAGE CLASSIFICATION GUARDS
# ============================================================


def is_content_slug_not_profile_page(
    url: str,
) -> bool:
    """
    Reject article/product/content slugs that merely contain a leadership
    keyword such as 'management'.

    Examples that must NOT be classified as management pages:
        /chrome-device-management-license-...
        /project-management/
        /google-cloud-identity-management/
    """
    terminal = get_terminal_segment(url)

    if not terminal:
        return False

    article_signals = (
        "license",
        "solution",
        "services",
        "service",
        "tool",
        "platform",
        "system",
        "product",
        "workspace",
        "cloud",
        "freshsales",
        "greythr",
        "jumpcloud",
        "microsoft",
        "google",
        "chrome",
        "document",
        "project",
        "payroll",
        "identity",
        "device",
        "access",
        "task",
        "workspace",
        "learn-all",
        "things-about",
        "updates-with",
    )

    # Long compound slugs are usually content/product pages rather than
    # dedicated leadership/management pages.
    normalized = terminal.casefold().replace("-", " ")

    if len(normalized.split()) >= 4:
        return True

    return any(signal in normalized for signal in article_signals)


# ============================================================
# CLASSIFY PAGE
# ============================================================


def classify_page(
    url: str,
    anchor_text: str,
    company_homepage: str,
) -> tuple[int, str]:
    """
    Classify a page using URL and anchor evidence.

    Unlike the previous version, a useful page can be discovered even
    when the homepage does not expose a perfect anchor label.
    """
    if is_homepage(
        url,
        company_homepage,
    ):
        return 0, "other"

    if is_excluded_path(url):
        return 0, "other"

    terminal = get_terminal_segment(url)

    if not terminal:
        return 0, "other"

    # Reject content/product/article slugs before keyword fallback.
    if is_content_slug_not_profile_page(url):
        return 0, "other"

    # --------------------------------------------------------
    # First: exact terminal classification.
    # --------------------------------------------------------

    for page_type, patterns in config.PAGE_PATTERNS.items():
        if terminal in patterns:
            score = config.PAGE_TYPE_SCORES[page_type]
            return score, page_type

    # --------------------------------------------------------
    # Second: direct anchor classification.
    # --------------------------------------------------------

    anchor = clean_text(anchor_text).casefold()

    strong_anchor_types = {
        "leadership": {
            "leadership",
            "leadership team",
            "senior leadership",
        },
        "management": {
            "management",
            "management team",
            "management profiles",
        },
        "executive": {
            "executive",
            "executive team",
            "executive leadership",
        },
        "founder": {
            "founder",
            "founders",
            "founding team",
        },
        "board": {
            "board",
            "board of directors",
            "board members",
        },
        "director": {
            "director",
            "directors",
        },
        "team": {
            "our team",
            "our people",
            "meet the team",
            "team members",
        },
        "contact": {
            "contact",
            "contact us",
            "get in touch",
            "reach us",
            "talk to us",
        },
        "about": {
            "about us",
            "about company",
            "company profile",
            "company overview",
            "who we are",
        },
    }

    for page_type, anchors in strong_anchor_types.items():
        if anchor in anchors:
            score = config.PAGE_TYPE_SCORES.get(
                page_type,
                config.MIN_PAGE_SCORE,
            )
            return score, page_type

    # --------------------------------------------------------
    # Third: path keyword classification.
    #
    # This is used only as bounded fallback for sitemap/common
    # paths. It does not classify arbitrary child pages solely
    # because they live under a parent directory.
    # --------------------------------------------------------

    segments_text = [
        segment.casefold().replace("-", " ").replace("_", " ")
        for segment in get_path_segments(url)
    ]

    exact_path_types = {
        "leadership": "leadership",
        "management": "management",
        "management team": "management",
        "management profiles": "management",
        "executive": "executive",
        "executive team": "executive",
        "executive leadership": "executive",
        "board": "board",
        "board of directors": "board",
        "directors": "director",
        "founder": "founder",
        "founders": "founder",
        "our team": "team",
        "team": "team",
        "our people": "team",
        "people": "team",
        "contact": "contact",
        "contact us": "contact",
        "about": "about",
        "about us": "about",
        "company profile": "about",
        "who we are": "about",
    }

    if len(segments_text) == 1:
        page_type = exact_path_types.get(segments_text[0])

        if page_type:
            score = config.PAGE_TYPE_SCORES.get(
                page_type,
                config.MIN_PAGE_SCORE,
            )
            return score, page_type

    return 0, "other"


# ============================================================
# FETCH
# ============================================================


def fetch_page(
    url: str,
) -> tuple[
    requests.Response | None,
    str,
]:
    """
    Download HTML.

    First use normal TLS verification. If certificate verification fails,
    retry once with verification disabled for public-page discovery only.
    """
    try:
        response = session.get(
            url,
            timeout=config.REQUEST_TIMEOUT,
            allow_redirects=True,
        )
    except requests.exceptions.SSLError as error:
        print(f"    [WARNING] SSL verification failed: {error}")

        try:
            requests.packages.urllib3.disable_warnings(
                category=requests.packages.urllib3.exceptions.InsecureRequestWarning
            )
            response = session.get(
                url,
                timeout=config.REQUEST_TIMEOUT,
                allow_redirects=True,
                verify=False,
            )
            print("    [INFO] SSL fallback request succeeded.")
        except requests.RequestException as fallback_error:
            print(f"    [ERROR] {fallback_error}")
            return None, ""
    except requests.RequestException as error:
        print(f"    [ERROR] {error}")
        return None, ""

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    if response.status_code >= 400 or "text/html" not in content_type:
        return response, ""

    return response, response.text


# ============================================================
# LINK DISCOVERY
# ============================================================


def extract_relevant_links(
    html: str,
    homepage: str,
) -> list[dict]:
    """Extract high-value internal pages from navigation areas."""
    soup = BeautifulSoup(
        html,
        "lxml",
    )

    links: list[dict] = []
    seen: set[str] = set()

    containers = soup.find_all(
        ["nav", "header", "main", "footer"],
        limit=12,
    )

    anchors = []

    for container in containers:
        anchors.extend(
            container.find_all(
                "a",
                href=True,
                limit=config.MAX_LINKS_FROM_HOMEPAGE,
            )
        )

    if not anchors:
        anchors = soup.find_all(
            "a",
            href=True,
        )

    unique_anchors = []
    anchor_ids: set[int] = set()

    for anchor in anchors:
        identifier = id(anchor)

        if identifier in anchor_ids:
            continue

        anchor_ids.add(identifier)
        unique_anchors.append(anchor)

    anchors = unique_anchors[: config.MAX_LINKS_FROM_HOMEPAGE * 2]

    for anchor in anchors:
        href = anchor.get(
            "href",
            "",
        ).strip()

        anchor_text = clean_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        if not href:
            continue

        if href.lower().startswith(
            (
                "javascript:",
                "mailto:",
                "tel:",
                "sms:",
                "data:",
                "#",
            )
        ):
            continue

        absolute_url = normalize_url(
            href,
            homepage,
        )

        if not is_valid_url(absolute_url):
            continue

        if not is_same_domain(
            absolute_url,
            homepage,
        ):
            continue

        if is_excluded_path(absolute_url):
            continue

        if absolute_url in seen:
            continue

        score, page_type = classify_page(
            absolute_url,
            anchor_text,
            homepage,
        )

        if score < config.MIN_PAGE_SCORE:
            continue

        seen.add(absolute_url)

        links.append(
            {
                "url": absolute_url,
                "page_type": page_type,
                "score": score,
                "anchor_text": anchor_text,
            }
        )

    links.sort(
        key=lambda item: (
            -item["score"],
            item["url"],
        )
    )

    return links


# ============================================================
# SITEMAP
# ============================================================


def extract_sitemap_urls(
    xml_text: str,
) -> list[str]:
    """Extract URLs from a sitemap or sitemap index."""
    soup = BeautifulSoup(
        xml_text,
        "xml",
    )

    urls: list[str] = []

    for loc in soup.find_all("loc"):
        value = clean_text(
            loc.get_text(
                " ",
                strip=True,
            )
        )

        if value:
            urls.append(value)

    return urls


def fetch_sitemap_urls(
    homepage: str,
) -> list[str]:
    """
    Read standard sitemap.xml and robots.txt sitemap declarations.

    Bounded to keep discovery lightweight.
    """
    sitemap_candidates = [
        urljoin(
            homepage,
            "/sitemap.xml",
        ),
        urljoin(
            homepage,
            "/sitemap_index.xml",
        ),
        urljoin(
            homepage,
            "/sitemap-index.xml",
        ),
    ]

    robots_url = urljoin(
        homepage,
        "/robots.txt",
    )

    try:
        robots = session.get(
            robots_url,
            timeout=config.REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        if robots.status_code < 400:
            for line in robots.text.splitlines():
                if line.casefold().startswith("sitemap:"):
                    value = clean_text(
                        line.split(
                            ":",
                            1,
                        )[1]
                    )

                    if value:
                        sitemap_candidates.append(value)
    except requests.RequestException:
        pass

    sitemap_candidates = list(dict.fromkeys(sitemap_candidates))

    collected: list[str] = []

    for sitemap_url in sitemap_candidates:
        try:
            response = session.get(
                sitemap_url,
                timeout=config.REQUEST_TIMEOUT,
                allow_redirects=True,
            )
        except requests.RequestException:
            continue

        if response.status_code >= 400:
            continue

        content_type = response.headers.get(
            "Content-Type",
            "",
        ).casefold()

        if (
            "xml" not in content_type
            and not response.text.lstrip().startswith("<?xml")
            and "<urlset" not in response.text[:1000].lower()
            and "<sitemapindex" not in response.text[:1000].lower()
        ):
            continue

        urls = extract_sitemap_urls(response.text)

        # If this is a sitemap index, follow a small number of child
        # sitemaps and only keep same-domain URLs.
        if "<sitemapindex" in response.text[:5000].lower():
            child_sitemaps = urls[:10]

            for child_url in child_sitemaps:
                child_url = normalize_url(child_url)

                if not child_url:
                    continue

                if not is_same_domain(
                    child_url,
                    homepage,
                ):
                    continue

                try:
                    child_response = session.get(
                        child_url,
                        timeout=config.REQUEST_TIMEOUT,
                        allow_redirects=True,
                    )
                except requests.RequestException:
                    continue

                if child_response.status_code >= 400:
                    continue

                collected.extend(extract_sitemap_urls(child_response.text))
        else:
            collected.extend(urls)

    return list(dict.fromkeys(collected))


# ============================================================
# COMMON PATH DISCOVERY
# ============================================================


COMMON_PATHS = (
    (
        "company-profile",
        "about",
    ),
    (
        "corporate-profile",
        "about",
    ),
    (
        "our-company",
        "about",
    ),
    (
        "about-company",
        "about",
    ),
    (
        "contactus",
        "contact",
    ),
    (
        "leadership",
        "leadership",
    ),
    (
        "about-us",
        "about",
    ),
    (
        "about",
        "about",
    ),
    (
        "company",
        "about",
    ),
    (
        "who-we-are",
        "about",
    ),
    (
        "management",
        "management",
    ),
    (
        "management-team",
        "management",
    ),
    (
        "executive-team",
        "executive",
    ),
    (
        "executives",
        "executive",
    ),
    (
        "our-team",
        "team",
    ),
    (
        "team",
        "team",
    ),
    (
        "our-people",
        "team",
    ),
    (
        "people",
        "team",
    ),
    (
        "board-of-directors",
        "board",
    ),
    (
        "directors",
        "director",
    ),
    (
        "founders",
        "founder",
    ),
    (
        "founder",
        "founder",
    ),
    (
        "contact-us",
        "contact",
    ),
    (
        "contact",
        "contact",
    ),
)


def probe_common_paths(
    homepage: str,
) -> list[dict]:
    """Probe a small set of common company pages."""
    results: list[dict] = []
    seen: set[str] = set()

    for path, expected_type in COMMON_PATHS:
        candidate = normalize_url(
            f"/{path}",
            homepage,
        )

        if not candidate:
            continue

        if candidate in seen:
            continue

        seen.add(candidate)

        try:
            response = session.get(
                candidate,
                timeout=config.REQUEST_TIMEOUT,
                allow_redirects=True,
            )
        except requests.RequestException:
            continue

        if response.status_code >= 400:
            continue

        final_url = normalize_url(response.url) or candidate

        if not is_same_domain(
            final_url,
            homepage,
        ):
            continue

        score, page_type = classify_page(
            final_url,
            path.replace(
                "-",
                " ",
            ),
            homepage,
        )

        if page_type == "other":
            page_type = expected_type

        if score < config.MIN_PAGE_SCORE:
            score = config.PAGE_TYPE_SCORES.get(
                page_type,
                config.MIN_PAGE_SCORE,
            )

        if score < config.MIN_PAGE_SCORE or is_excluded_path(final_url):
            continue

        results.append(
            {
                "url": final_url,
                "page_type": page_type,
                "score": score,
                "anchor_text": path.replace(
                    "-",
                    " ",
                ).title(),
            }
        )

    return results


# ============================================================
# CANDIDATE MERGE
# ============================================================


def merge_candidates(
    *candidate_sets: list[dict],
) -> list[dict]:
    """Merge candidates by URL, keeping the strongest classification."""
    merged: dict[str, dict] = {}

    for candidates in candidate_sets:
        for candidate in candidates:
            url = candidate["url"]

            previous = merged.get(url)

            if previous is None:
                merged[url] = candidate
                continue

            if candidate["score"] > previous["score"]:
                merged[url] = candidate
                continue

            if candidate["score"] == previous["score"] and len(
                candidate.get(
                    "anchor_text",
                    "",
                )
            ) > len(
                previous.get(
                    "anchor_text",
                    "",
                )
            ):
                merged[url] = candidate

    return sorted(
        merged.values(),
        key=lambda item: (
            -item["score"],
            item["url"],
        ),
    )


# ============================================================
# LOAD COMPANIES
# ============================================================


def load_companies() -> list[dict]:
    """Load reachable companies from Phase 1 output."""
    input_file = config.COMPANIES_OUTPUT_FILE

    if not input_file.exists():
        print("[ERROR] Phase 1 output not found:")
        print(input_file)
        return []

    try:
        with open(
            input_file,
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            if not reader.fieldnames:
                print("[ERROR] CSV has no header.")
                return []

            return [
                row
                for row in reader
                if row.get(
                    "reachable",
                    "",
                )
                .strip()
                .upper()
                == "YES"
            ]

    except OSError as error:
        print("[ERROR] Could not read companies:")
        print(error)
        return []


# ============================================================
# CRAWL COMPANY
# ============================================================


def crawl_company(
    company: dict,
) -> list[dict]:
    """Discover CXO-relevant pages using bounded strategies."""
    company_name = company.get(
        "company_name",
        "",
    )

    homepage = (
        company.get(
            "final_url",
            "",
        )
        or company.get(
            "final_website",
            "",
        )
        or company.get(
            "normalized_website",
            "",
        )
        or company.get(
            "website",
            "",
        )
    )

    homepage = normalize_url(homepage)

    if not homepage:
        return []

    print()
    print("    Crawling:")
    print(f"    {homepage}")

    # --------------------------------------------------------
    # Homepage
    # --------------------------------------------------------

    response, html = fetch_page(homepage)

    if not response or not html:
        print("    [WARNING] Homepage could not be read.")

        sitemap_candidates = fetch_sitemap_urls(homepage)

        common_candidates = probe_common_paths(homepage)

        links = merge_candidates(
            common_candidates,
            [
                {
                    "url": url,
                    "page_type": classify_page(
                        url,
                        "",
                        homepage,
                    )[1],
                    "score": classify_page(
                        url,
                        "",
                        homepage,
                    )[0],
                    "anchor_text": "",
                }
                for url in sitemap_candidates
                if is_same_domain(
                    url,
                    homepage,
                )
                and not is_excluded_path(url)
            ],
        )
    else:
        final_homepage = normalize_url(response.url) or homepage

        homepage_links = extract_relevant_links(
            html,
            final_homepage,
        )

        sitemap_urls = fetch_sitemap_urls(final_homepage)

        sitemap_candidates: list[dict] = []

        for url in sitemap_urls:
            normalized = normalize_url(url)

            if not normalized:
                continue

            if not is_same_domain(
                normalized,
                final_homepage,
            ):
                continue

            score, page_type = classify_page(
                normalized,
                "",
                final_homepage,
            )

            if score < config.MIN_PAGE_SCORE:
                continue

            sitemap_candidates.append(
                {
                    "url": normalized,
                    "page_type": page_type,
                    "score": score,
                    "anchor_text": "",
                }
            )

        common_candidates = probe_common_paths(final_homepage)

        links = merge_candidates(
            homepage_links,
            sitemap_candidates,
            common_candidates,
        )

    links = links[: config.MAX_PAGES_PER_COMPANY]

    print("    CXO-relevant pages: " f"{len(links)}")

    company_domain = extract_domain(homepage)

    return [
        {
            "company_name": company_name,
            "company_domain": company_domain,
            "homepage": homepage,
            "page_url": link["url"],
            "page_type": link["page_type"],
            "score": link["score"],
            "anchor_text": link["anchor_text"],
        }
        for link in links
    ]


# ============================================================
# SAVE
# ============================================================


def save_results(
    results: list[dict],
) -> None:
    """Save discovery output."""
    config.OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = config.WEBSITE_PAGES_OUTPUT_FILE

    fieldnames = [
        "company_name",
        "company_domain",
        "homepage",
        "page_url",
        "page_type",
        "score",
        "anchor_text",
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
        writer.writerows(results)

    print()
    print("=" * 70)
    print("CXO-FOCUSED PAGE DISCOVERY OUTPUT")
    print("=" * 70)
    print(f"File: {output_file}")
    print(f"Pages: {len(results)}")


# ============================================================
# SUMMARY
# ============================================================


def display_summary(
    results: list[dict],
) -> None:
    """Display page-type statistics."""
    print()
    print("=" * 70)
    print("DISCOVERY SUMMARY")
    print("=" * 70)

    if not results:
        print("No relevant pages discovered.")
        print(
            "Phase 3 should not run until at least one " "company page is discovered."
        )
        return

    counts: dict[str, int] = {}

    for result in results:
        page_type = result.get(
            "page_type",
            "other",
        )

        counts[page_type] = (
            counts.get(
                page_type,
                0,
            )
            + 1
        )

    for page_type, count in sorted(counts.items()):
        print(f"{page_type:<15}: " f"{count}")


# ============================================================
# MAIN
# ============================================================


def main() -> None:
    """Run Phase 2.7."""
    print()
    print("=" * 70)
    print("CXO GOOGLE SCRAPER")
    print("PHASE 2.7 - PRECISION WEBSITE DISCOVERY")
    print("=" * 70)

    print()
    print("Cost policy:")
    print("Google Places API : NOT USED")
    print("Google Search API : NOT USED")
    print("Paid API          : NOT USED")
    print("Proxy             : NOT USED")
    print("Scraping service  : NOT USED")

    companies = load_companies()

    if not companies:
        print()
        print("[ERROR] No reachable companies.")
        return

    print()
    print(f"Companies loaded: " f"{len(companies)}")

    all_results: list[dict] = []

    for index, company in enumerate(
        companies,
        start=1,
    ):
        print()
        print("-" * 70)

        print(f"COMPANY " f"{index}/" f"{len(companies)}")

        print(f"Company: " f"{company.get('company_name', '')}")

        results = crawl_company(company)

        all_results.extend(results)

        if index < len(companies):
            time.sleep(config.REQUEST_DELAY)

    # Global de-duplication.
    unique_results: dict[str, dict] = {}

    for result in all_results:
        key = (
            result["company_name"].casefold(),
            result["page_url"].casefold(),
        )

        previous = unique_results.get(key)

        if previous is None or result["score"] > previous["score"]:
            unique_results[key] = result

    all_results = sorted(
        unique_results.values(),
        key=lambda item: (
            item["company_name"].casefold(),
            -item["score"],
            item["page_url"],
        ),
    )

    display_summary(all_results)

    save_results(all_results)

    print()
    print("=" * 70)
    print("PHASE 2.7 COMPLETE")
    print("=" * 70)

    print()
    print("Precision CXO-focused website discovery completed.")

    print()
    print("Do NOT run Phase 3 yet.")

    print("Inspect website_pages.csv first.")


if __name__ == "__main__":
    main()
