"""Generate static publication cards from data/publications.json."""

from __future__ import annotations

import html
import json
import re
import textwrap
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "publications.json"
OUTPUT_PATH = ROOT / "publications.html"
START_MARKER = "          <!-- PUBLICATIONS:START -->"
END_MARKER = "          <!-- PUBLICATIONS:END -->"


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def wrap_text(value: str, indent: str, width: int = 92) -> str:
    lines = textwrap.wrap(value, width=width, break_long_words=False, break_on_hyphens=False)
    return f"\n{indent}".join(escape(line) for line in lines)


def format_authors(authors: list[dict[str, Any]]) -> str:
    formatted = [
        f"<strong>{escape(author['name'])}</strong>"
        if author.get("highlight")
        else escape(author["name"])
        for author in authors
    ]

    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]} and {formatted[1]}"
    return f"{', '.join(formatted[:-1])}, and {formatted[-1]}"


def validate(publications: list[dict[str, Any]]) -> None:
    required = {
        "id",
        "year",
        "topic",
        "type",
        "title",
        "authors",
        "venue",
        "links",
    }
    seen_ids: set[str] = set()

    for index, publication in enumerate(publications):
        missing = required - publication.keys()
        if missing:
            raise ValueError(f"Publication {index} is missing: {', '.join(sorted(missing))}")
        if publication["id"] in seen_ids:
            raise ValueError(f"Duplicate publication id: {publication['id']}")
        if not publication["authors"]:
            raise ValueError(f"Publication {publication['id']} has no authors")
        if not publication["links"]:
            raise ValueError(f"Publication {publication['id']} has no links")
        seen_ids.add(publication["id"])


def render_links(links: list[dict[str, Any]]) -> str:
    rendered = []
    for link in links:
        classes = "action-link primary" if link.get("primary") else "action-link"
        rendered.append(
            f'              <a class="{classes}" href="{escape(link["url"])}">'
            f'{escape(link["label"])}</a>'
        )
    return "\n".join(rendered)


def render_publication(publication: dict[str, Any]) -> str:
    authors = format_authors(publication["authors"])
    details = render_details(publication)

    return f"""          <article class="library-item reveal" id="{escape(publication['id'])}" data-topic="{escape(publication['topic'])}">
            <div class="library-year">{escape(publication['year'])}</div>
            <div>
              <span class="library-type">{escape(publication['type'])}</span>
              <h2>{escape(publication['title'])}</h2>
              <p class="library-authors">
                {authors}
              </p>
              <p class="library-venue">{escape(publication['venue'])}</p>
{details}
            </div>
            <div class="library-actions">
{render_links(publication['links'])}
            </div>
          </article>"""


def render_details(publication: dict[str, Any]) -> str:
    abstract = publication.get("abstract")
    bibtex = publication.get("bibtex")
    if not abstract and not bibtex:
        return ""

    label = publication.get("detailsLabel", "Abstract & citation")
    parts = [
        '              <details class="paper-details">',
        f"                <summary>{escape(label)}</summary>",
        '                <div class="paper-details-content">',
    ]

    if abstract:
        abstract_label = publication.get("abstractLabel", "Abstract")
        wrapped = wrap_text(abstract, "                    ")
        parts.extend(
            [
                f"                  <h3>{escape(abstract_label)}</h3>",
                '                  <p class="paper-abstract">',
                f"                    {wrapped}",
                "                  </p>",
            ]
        )

    if bibtex:
        parts.extend(
            [
                "                  <h3>BibTeX</h3>",
                '                  <div class="citation-box">',
                f"                    <pre><code>{html.escape(bibtex)}</code></pre>",
                "                  </div>",
                '                  <button class="action-link copy-citation" type="button">Copy BibTeX</button>',
            ]
        )

    parts.extend(["                </div>", "              </details>"])
    return "\n".join(parts)


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    publications = payload["publications"]
    validate(publications)

    source = OUTPUT_PATH.read_text(encoding="utf-8")
    if source.count(START_MARKER) != 1 or source.count(END_MARKER) != 1:
        raise ValueError("Expected exactly one publication marker pair in publications.html")

    generated = "\n\n".join(render_publication(item) for item in publications)
    before, remainder = source.split(START_MARKER, 1)
    _, after = remainder.split(END_MARKER, 1)
    output = f"{before}{START_MARKER}\n{generated}\n{END_MARKER}{after}"
    output = re.sub(
        r"Showing <strong>\d+</strong>(?: selected)? publications",
        f"Showing <strong>{len(publications)}</strong> publications",
        output,
        count=1,
    )
    OUTPUT_PATH.write_text(output, encoding="utf-8", newline="\n")
    print(f"Generated {len(publications)} publications in {OUTPUT_PATH.name}")


if __name__ == "__main__":
    main()
