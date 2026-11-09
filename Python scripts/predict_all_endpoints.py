#!/usr/bin/env python3
"""Append full-title probability columns for all matched toxicity endpoints.

Default: read Data/micotoxilico_OG.csv and write Data/micotoxilico.csv.
Use --overwrite to replace previous results (a backup is created). Use --limit 5 --output preview.csv for a small test.
Each endpoint is predicted independently from SMILES, without observed context.
The default molecular limit is 512 tokens to accommodate this dataset's longer
structures. This extends the upstream helper's 120-token default; it does not
establish predictive accuracy for longer molecules. Structures are not truncated.
"""
import argparse
import csv
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent / "toxtransformer-research"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "Data/micotoxilico_OG.csv")
    parser.add_argument("--endpoints", type=Path, default=HERE / "Data/toxicity_property_matches.json")
    parser.add_argument("--output", type=Path, default=HERE / "Data/micotoxilico.csv")
    parser.add_argument("--log-dir", type=Path, default=HERE / "Excecution tracker")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace existing output and same-day logs; back up the output CSV")
    parser.add_argument("--limit", type=int, help="Test first N rows; requires separate --output")
    parser.add_argument("--max-selfies", type=int, default=512,
                        help="Molecular token limit (default: 512; upstream default: 120)")
    args = parser.parse_args()
    source = args.input.resolve()
    output = args.output.resolve()
    if source == output:
        parser.error("Input and output must differ; original data is never overwritten")
    if args.limit is not None and output == (HERE / "Data/micotoxilico.csv").resolve():
        parser.error("For --limit, choose a separate --output preview file")
    if args.limit is not None and (args.limit < 1 or source == output):
        parser.error("--limit requires a positive count and a separate --output")
    if args.max_selfies < 3:
        parser.error("--max-selfies must be at least 3")
    if output.exists() and not args.overwrite:
        parser.error("Output already exists; use --overwrite or choose a new --output")
    if output in (args.endpoints.resolve(), (REPO / "models/toxtransformer/properties.json").resolve()):
        parser.error("Output cannot overwrite an endpoint catalog")
    try:
        import torch
        from selfies import EncoderError
        from toxtransformer_research.checkpoint import (
            load_checkpoint, load_properties, predict_checkpoint, verify_manifest,
        )
    except ImportError as exc:
        parser.exit(1, f"Run using {REPO / '.venv/bin/python'}\n{exc}\n")

    checkpoint = REPO / "models/toxtransformer"
    manifest = verify_manifest(checkpoint, REPO / "artifacts/upstream-checkpoint.json")
    catalog = load_properties(checkpoint)
    endpoints = json.loads(args.endpoints.read_text(encoding="utf-8"))
    if not endpoints or catalog is None:
        parser.error("Missing endpoint entries or checkpoint catalog")
    for entry in endpoints:
        index = entry["index"]
        if not isinstance(index, int) or not 0 <= index < len(catalog):
            parser.error(f"Invalid index: {index}")
        if any(entry.get(key) != catalog[index].get(key)
               for key in ("property_id", "title", "source")):
            parser.error(f"Endpoint {index} differs from the checkpoint catalog")
    titles = [entry["title"] for entry in endpoints]
    if (not all(isinstance(t, str) and t for t in titles)
            or len(set(titles)) != len(titles)
            or len({e['index'] for e in endpoints}) != len(endpoints)):
        parser.error("Endpoint indices and full titles must be nonempty and unique")
    initial_hash = digest(source)
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        if not fields or "SMILES" not in fields or len(set(fields)) != len(fields):
            parser.error("CSV must have unique headers and a SMILES column")
        rows = list(reader)
    if set(fields) & set(titles):
        parser.error("Prediction title columns already exist; use an original input/backup")
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        parser.error("Malformed CSV row; no files updated")
    if args.limit:
        rows = rows[:args.limit]

    stamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d")
    args.log_dir.mkdir(parents=True, exist_ok=True)
    run_path = args.log_dir / f"micotox_run_{stamp}.json"
    error_path = args.log_dir / f"micotox_errors_{stamp}.json"
    if not args.overwrite and (run_path.exists() or error_path.exists()):
        parser.error("Same-day logs exist; use --overwrite or a separate --log-dir")
    torch.set_num_threads(1)
    model = load_checkpoint(checkpoint, "cpu")
    if model.tokenizer.num_assays != len(catalog):
        raise ValueError("Model and endpoint catalog sizes differ")
    output.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if output.exists():
        backup = output.with_name(f"{output.stem}_backup_{stamp}{output.suffix}")
        number = 2
        while backup.exists():
            backup = output.with_name(f"{output.stem}_backup_{stamp}_{number}{output.suffix}")
            number += 1
        shutil.copy2(output, backup)
        if digest(backup) != digest(output):
            raise RuntimeError("Output backup verification failed")
    metadata = dict(status="running", input=str(source), output=str(output),
                    input_sha256=initial_hash, backup=str(backup) if backup else None,
                    endpoints=endpoints, max_selfies=args.max_selfies, n_context=0,
                    checkpoint_manifest=manifest, rows_requested=len(rows),
                    interpretation="Independent structure-only class-1 probabilities. "
                    "Blank cells indicate processing failures; see errors file.")
    cache, errors = {}, []
    completed = successful = 0
    temp_path = None
    run_path.write_text(json.dumps(metadata, indent=2) + "\n")
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=output.parent, prefix=output.stem + ".partial_",
                                         suffix=".csv", delete=False) as stream:
            temp_path = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=fields + titles)
            writer.writeheader()
            for row_number, row in enumerate(rows, 1):
                smiles = row["SMILES"].strip()
                if smiles not in cache:
                    predictions = {}
                    for entry in endpoints:
                        try:
                            if not smiles:
                                raise ValueError("Missing SMILES")
                            p = predict_checkpoint(model, smiles, entry["index"],
                                                   max_selfies=args.max_selfies)["probability"]
                            if not math.isfinite(p) or not 0 <= p <= 1:
                                raise RuntimeError("Invalid model probability")
                            predictions[entry["index"]] = (p, None)
                        except (ValueError, KeyError, IndexError, EncoderError) as exc:
                            predictions[entry["index"]] = ("", f"{type(exc).__name__}: {exc}")
                    cache[smiles] = predictions
                for entry in endpoints:
                    p, error = cache[smiles][entry["index"]]
                    row[entry["title"]] = p
                    if error:
                        errors.append(dict(data_row=row_number, smiles=smiles,
                                           index=entry["index"], title=entry["title"], error=error))
                    else:
                        successful += 1
                writer.writerow(row)
                stream.flush()
                completed = row_number
                if completed == 1 or completed % 50 == 0 or completed == len(rows):
                    print(f"{completed}/{len(rows)} rows; {successful} probabilities; "
                          f"{len(errors)} failed cells", flush=True)
        # Check serialized values and row order before replacing the original.
        with temp_path.open(encoding="utf-8", newline="") as stream:
            saved = list(csv.DictReader(stream))
        if len(saved) != len(rows) or any(
                any(saved_row[k] != str(row[k]) for k in fields + titles)
                for saved_row, row in zip(saved, rows)):
            raise RuntimeError("CSV round-trip verification failed")
        if digest(source) != initial_hash:
            raise RuntimeError("Input changed during prediction; refusing to replace it")
        error_path.write_text(json.dumps(errors, indent=2) + "\n")
        temp_path.replace(output)
        metadata["status"] = "complete"
        metadata["output_sha256"] = digest(output)
    finally:
        metadata.update(rows_completed=completed, successful_cells=successful,
                        failed_cells=len(errors), errors_file=str(error_path))
        if metadata["status"] != "complete":
            metadata.update(status="incomplete", partial_csv=str(temp_path))
            error_path.write_text(json.dumps(errors, indent=2) + "\n")
        run_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Saved {output}\nRun metadata: {run_path}\nError details: {error_path}")
    if backup:
        print(f"Original backup: {backup}")


if __name__ == "__main__":
    main()
