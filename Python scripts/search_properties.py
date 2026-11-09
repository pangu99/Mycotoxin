#!/usr/bin/env python3
"""Search all ToxTransformer endpoint titles and save full matching entries.

Run: python3 search_properties.py
Matches substrings without regard to case: genotoxic also matches genotoxicity.
Uses Python's standard library; no model loading or prediction is needed.
"""

import argparse
import json
from pathlib import Path


def main():
    folder = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", type=Path,
        default=folder.parent / "toxtransformer-research/models/toxtransformer/properties.json",
    )
    parser.add_argument("--keywords", nargs="+", default=["genotoxic", "carcinogenic", "mutagenic"])
    parser.add_argument("--output", type=Path, default=folder / "Data/toxicity_property_matches.json")
    args = parser.parse_args()
    if args.output.resolve() == args.catalog.resolve():
        parser.error("Output must not overwrite the source catalog")
    keywords = list(dict.fromkeys(word.strip().casefold() for word in args.keywords))
    if not all(keywords):
        parser.error("Keywords cannot be empty")
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    matches = []
    for entry in catalog:
        title = entry.get("title")
        if not isinstance(title, str):
            continue
        matched = [word for word in keywords if word in title.casefold()]
        if matched:
            matches.append({**entry, "matched_keywords": matched})
    matches.sort(key=lambda entry: entry["index"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(matches, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Searched {len(catalog)} endpoints; found {len(matches)} matching endpoints.")
    for keyword in keywords:
        print(f"  {keyword}: {sum(keyword in entry['matched_keywords'] for entry in matches)}")
    print(f"Saved full titles, indices, property IDs, sources, and matched keywords to {args.output}")


if __name__ == "__main__":
    main()
