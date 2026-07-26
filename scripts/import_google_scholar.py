"""Import publication-list metadata from a public Google Scholar profile."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "publications.json"
PROFILE_ID = "IiMXAxUAAAAJ"
PROFILE_URL = (
    "https://scholar.google.com/citations"
    f"?user={PROFILE_ID}&hl=en&pagesize=100"
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.casefold())


def slugify(title: str) -> str:
    ascii_title = (
        unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.casefold()).strip("-")
    return slug[:72] or "publication"


def classify_type(venue: str, title: str) -> str:
    value = f"{venue} {title}".casefold()
    if "arxiv" in value:
        return "Preprint · arXiv"
    if "patent" in value:
        return "Patent"
    if any(word in value for word in ("thesis", "faculté", "université de biskra")):
        return "Thesis"
    if any(word in value for word in ("conference", "proceedings", "workshop", "conf.")):
        return "Conference paper"
    if venue:
        return "Journal or publication"
    return "Publication"


def classify_topic(title: str, venue: str) -> str:
    value = f"{title} {venue}".casefold()
    if any(word in value for word in ("hyperspectral", "remote sensing")):
        return "remote"
    if any(
        word in value
        for word in ("medical", "lung", "lesion", "biomedical", "severity scoring")
    ):
        return "medical"
    if any(
        word in value
        for word in (
            "face",
            "facial",
            "image",
            "video",
            "vision",
            "kinship",
            "gait",
            "drowsiness",
            "personality",
            "spoofing",
            "object detection",
            "tracking",
            "background subtraction",
            "age estimation",
        )
    ):
        return "vision"
    return "other"


def parse_authors(author_text: str) -> list[dict[str, Any]]:
    names = [name.strip() for name in author_text.split(",") if name.strip()]
    return [
        {
            "name": name,
            **({"highlight": True} if "bekhouche" in name.casefold() else {}),
        }
        for name in names
    ]


def fetch_profile() -> BeautifulSoup:
    request = Request(PROFILE_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        content = response.read()
    soup = BeautifulSoup(content, "html.parser")
    if not soup.select("tr.gsc_a_tr"):
        raise RuntimeError("Scholar returned no publications; the request may be blocked")
    return soup


def parse_rows(soup: BeautifulSoup) -> list[dict[str, Any]]:
    publications = []
    used_ids: set[str] = set()
    seen_titles: set[str] = set()

    for row in soup.select("tr.gsc_a_tr"):
        title_link = row.select_one("a.gsc_a_at")
        metadata = row.select("div.gs_gray")
        if title_link is None or not metadata:
            continue

        title = title_link.get_text(" ", strip=True)
        normalized = normalize_title(title)
        if normalized in seen_titles:
            continue
        seen_titles.add(normalized)

        author_text = metadata[0].get_text(" ", strip=True)
        venue = metadata[1].get_text(" ", strip=True) if len(metadata) > 1 else ""
        year_element = row.select_one(".gsc_a_y span")
        year_text = year_element.get_text(strip=True) if year_element else ""
        year: int | str = int(year_text) if year_text.isdigit() else "n.d."
        citation_link = row.select_one("a.gsc_a_ac")
        citation_text = citation_link.get_text(strip=True) if citation_link else ""
        citations = int(citation_text) if citation_text.isdigit() else 0
        scholar_url = urljoin("https://scholar.google.com", title_link.get("href", ""))
        cited_by_url = (
            urljoin("https://scholar.google.com", citation_link.get("href", ""))
            if citation_link and citation_link.get("href")
            else None
        )

        base_id = slugify(title)
        publication_id = base_id
        suffix = 2
        while publication_id in used_ids:
            publication_id = f"{base_id}-{suffix}"
            suffix += 1
        used_ids.add(publication_id)

        links = [{"label": "Scholar", "url": scholar_url, "primary": True}]
        if cited_by_url:
            links.append({"label": f"Cited by {citations}", "url": cited_by_url})

        publications.append(
            {
                "id": publication_id,
                "year": year,
                "topic": classify_topic(title, venue),
                "type": classify_type(venue, title),
                "title": title,
                "authors": parse_authors(author_text),
                "venue": venue or "Venue not listed on Google Scholar",
                "links": links,
                "metadataStatus": "scholar-list",
                "scholar": {
                    "profileId": PROFILE_ID,
                    "url": scholar_url,
                    "authors": author_text,
                    "authorsTruncated": "..." in author_text or "…" in author_text,
                    "venue": venue,
                    "year": year,
                    "citations": citations,
                    "citedByUrl": cited_by_url,
                },
            }
        )

    return publications


def merge_publications(
    curated: list[dict[str, Any]], scholar: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    curated_by_title = {normalize_title(item["title"]): item for item in curated}
    merged = []

    for scholar_item in scholar:
        normalized = normalize_title(scholar_item["title"])
        if normalized in curated_by_title:
            item = curated_by_title.pop(normalized)
            item["scholar"] = scholar_item["scholar"]
            merged.append(item)
        else:
            merged.append(scholar_item)

    merged.extend(curated_by_title.values())

    def sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
        year = item["year"] if isinstance(item["year"], int) else 0
        citations = item.get("scholar", {}).get("citations", 0)
        return (-year, -citations, item["title"].casefold())

    return sorted(merged, key=sort_key)


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    scholar_publications = parse_rows(fetch_profile())
    payload["publications"] = merge_publications(
        payload["publications"], scholar_publications
    )
    payload["lastUpdated"] = "2026-07-26"
    payload["scholarProfile"] = {
        "id": PROFILE_ID,
        "url": PROFILE_URL,
        "rowsParsed": len(scholar_publications),
        "note": "Exact duplicate titles are imported once.",
    }
    DATA_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Imported {len(scholar_publications)} unique Scholar publications")


if __name__ == "__main__":
    main()
