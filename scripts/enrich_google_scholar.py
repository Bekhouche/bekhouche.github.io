"""Enrich imported publications from their Google Scholar detail records."""

from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "publications.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)


def parse_authors(author_text: str) -> list[dict[str, Any]]:
    return [
        {
            "name": name.strip(),
            **({"highlight": True} if "bekhouche" in name.casefold() else {}),
        }
        for name in author_text.split(",")
        if name.strip()
    ]


def clean_description(value: str) -> str:
    cleaned = html.unescape(value)
    for command in ("textbf", "emph", "textit", "mathrm", "operatorname"):
        cleaned = re.sub(rf"\\{command}\{{([^{{}}]*)\}}", r"\1", cleaned)
    return cleaned.replace(r"\%", "%").replace(r"\_", "_")


def fetch_detail(url: str) -> tuple[dict[str, str], str | None]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        soup = BeautifulSoup(response.read(), "html.parser")

    fields: dict[str, str] = {}
    for label in soup.select(".gsc_oci_field"):
        value = label.find_next_sibling(class_="gsc_oci_value")
        if value:
            fields[label.get_text(" ", strip=True)] = value.get_text(" ", strip=True)

    if not fields:
        raise RuntimeError("Scholar returned no detail fields")

    pdf_link = soup.select_one(".gsc_oci_title_ggi a")
    pdf_url = (
        urljoin("https://scholar.google.com", pdf_link.get("href", ""))
        if pdf_link
        else None
    )
    return fields, pdf_url


def citation_key(publication: dict[str, Any], authors: list[dict[str, Any]]) -> str:
    surname = re.sub(r"[^A-Za-z0-9]", "", authors[0]["name"].split()[-1])
    year = publication["year"] if isinstance(publication["year"], int) else "ND"
    words = re.findall(r"[A-Za-z0-9]+", publication["title"])
    keyword = "".join(words[:2])[:20]
    return f"{surname}{year}{keyword}"


def bibtex_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("&", "\\&")


def build_bibtex(
    publication: dict[str, Any], fields: dict[str, str], authors: list[dict[str, Any]]
) -> str:
    journal = fields.get("Journal")
    conference = fields.get("Conference")
    if journal and "arxiv" not in journal.casefold():
        entry_type = "article"
    elif conference:
        entry_type = "inproceedings"
    else:
        entry_type = "misc"

    lines = [
        f"@{entry_type}{{{citation_key(publication, authors)},",
        f"  title  = {{{bibtex_value(publication['title'])}}},",
        "  author = {"
        + " and ".join(bibtex_value(author["name"]) for author in authors)
        + "},",
    ]

    mappings = [
        ("Journal", "journal"),
        ("Conference", "booktitle"),
        ("Book", "booktitle"),
        ("Volume", "volume"),
        ("Issue", "number"),
        ("Pages", "pages"),
        ("Publisher", "publisher"),
        ("DOI", "doi"),
    ]
    for source, bibtex_name in mappings:
        value = fields.get(source)
        if value:
            lines.append(f"  {bibtex_name:<7}= {{{bibtex_value(value)}}},")

    if isinstance(publication["year"], int):
        lines.append(f"  year   = {{{publication['year']}}},")

    arxiv_match = re.search(r"arXiv:(\d{4}\.\d{4,5})", journal or "", re.IGNORECASE)
    if arxiv_match:
        lines.extend(
            [
                f"  eprint = {{{arxiv_match.group(1)}}},",
                "  archivePrefix = {arXiv},",
            ]
        )

    lines.append(f"  url    = {{{publication['scholar']['url']}}}")
    lines.append("}")
    return "\n".join(lines)


def build_links(
    publication: dict[str, Any], fields: dict[str, str], pdf_url: str | None
) -> list[dict[str, Any]]:
    links = []
    if pdf_url:
        links.append({"label": "PDF", "url": pdf_url, "primary": True})

    journal = fields.get("Journal", "")
    arxiv_match = re.search(r"arXiv:(\d{4}\.\d{4,5})", journal, re.IGNORECASE)
    if arxiv_match:
        links.append(
            {
                "label": "arXiv",
                "url": f"https://arxiv.org/abs/{arxiv_match.group(1)}",
                "primary": not pdf_url,
            }
        )

    doi = fields.get("DOI")
    if doi:
        links.append({"label": "DOI", "url": f"https://doi.org/{doi}"})

    links.append(
        {
            "label": "Scholar",
            "url": publication["scholar"]["url"],
            "primary": not links,
        }
    )
    cited_by_url = publication["scholar"].get("citedByUrl")
    citations = publication["scholar"].get("citations", 0)
    if cited_by_url:
        links.append({"label": f"Cited by {citations}", "url": cited_by_url})
    return links


def save(payload: dict[str, Any]) -> None:
    DATA_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    publications = payload["publications"]
    for publication in publications:
        if publication.get("abstract"):
            publication["abstract"] = clean_description(publication["abstract"])
    enriched = 0
    failed = 0

    for index, publication in enumerate(publications, start=1):
        scholar = publication.get("scholar")
        if not scholar or scholar.get("detailsFetched"):
            continue

        try:
            fields, pdf_url = fetch_detail(scholar["url"])
        except (HTTPError, URLError, TimeoutError, RuntimeError) as error:
            failed += 1
            print(f"[{index}/{len(publications)}] skipped {publication['id']}: {error}")
            time.sleep(1.5)
            continue

        full_authors = fields.get("Authors")
        authors = parse_authors(full_authors) if full_authors else publication["authors"]
        if full_authors:
            publication["authors"] = authors
            scholar["authors"] = full_authors
            scholar["authorsTruncated"] = False

        description = fields.get("Description")
        if description and not publication.get("abstract"):
            publication["abstractLabel"] = "Abstract"
            publication["abstract"] = clean_description(description)

        if not publication.get("bibtex"):
            publication["bibtex"] = build_bibtex(publication, fields, authors)

        if publication.get("metadataStatus") == "scholar-list":
            publication["links"] = build_links(publication, fields, pdf_url)

        scholar["details"] = fields
        scholar["pdfUrl"] = pdf_url
        scholar["detailsFetched"] = True
        publication["metadataStatus"] = "scholar-detail"
        enriched += 1
        print(f"[{index}/{len(publications)}] enriched {publication['id']}")

        if enriched % 5 == 0:
            save(payload)
        time.sleep(0.45)

    save(payload)
    print(f"Enriched {enriched} publications; {failed} failed")


if __name__ == "__main__":
    main()
