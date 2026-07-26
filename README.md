# Salah Eddine Bekhouche — Personal Website

A responsive academic and professional portfolio for AI and computer vision researcher
Salah Eddine Bekhouche.

## Local preview

The deployed site is static. Open `index.html` directly or serve the directory with any static
HTTP server.

## Structure

- `index.html` — content, metadata, and structured data
- `data/publications.json` — canonical publication metadata
- `scripts/generate_publications.py` — static publication-card generator
- `publications.html` — generated abstracts, links, and BibTeX citations
- `styles.css` — responsive layout, themes, and visual design
- `script.js` — mobile navigation, theme switching, and reveal effects

## Updating publications

Edit `data/publications.json`, then regenerate the static page:

```shell
conda run -n conda3.12 python scripts/generate_publications.py
```

Commit both the JSON source and generated `publications.html`.

To refresh the complete publication list from the public Google Scholar profile:

```shell
conda run -n conda3.12 python scripts/import_google_scholar.py
conda run -n conda3.12 python scripts/enrich_google_scholar.py
conda run -n conda3.12 python scripts/generate_publications.py
```

The importer merges by normalized title, so manually curated metadata is preserved. The detail
enricher resumes safely and skips records already fetched.

The website is deployed through GitHub Pages from this repository.
