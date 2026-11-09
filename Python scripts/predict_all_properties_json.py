#!/usr/bin/env python3
"""Predict every catalog property; experimentally labeled mutagenicity rows first.

One JSON per input row preserves duplicate records. Rerunning resumes partial
files and skips completed files. Experimental labels only select/prioritize rows;
they are never model context or exported metadata. Output JSON contains model
predictions and run information, without source-dataset fields.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import time

import torch
from selfies import EncoderError
from toxtransformer_research.checkpoint import (
    load_checkpoint, load_properties, predict_checkpoint, verify_manifest,
)
from toxtransformer_research.data import collate, encode_smiles

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent / "toxtransformer-research"


def save(path, value):
    if isinstance(value, dict):
        value = {key: item for key, item in value.items()
                 if key not in ('compound', 'data_row')}
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


@torch.inference_mode()
def batch_predict(model, encoded, indices):
    # Each batch member contains ONE independent endpoint query. Never chain
    # dummy labels as context for other property queries in a single sequence.
    inputs = collate([dict(selfies=encoded, pairs=[(i, 0)]) for i in indices], 'cpu')
    values = model(*inputs).float().softmax(-1)[:, 0, 1]
    if not torch.isfinite(values).all():
        raise RuntimeError('Nonfinite prediction')
    return values.tolist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT/'Data/micotoxilico_OG.csv')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'Data/experimental_mutagenicity')
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--max-selfies', type=int, default=512)
    parser.add_argument('--limit', type=int, help='First N compounds in priority order')
    parser.add_argument('--experimental-only', action='store_true')
    args = parser.parse_args()
    if args.batch_size < 1 or args.max_selfies < 3 or (args.limit is not None and args.limit < 1):
        parser.error('Batch size/limit must be positive and max-selfies at least 3')
    with args.input.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not {'SMILES', 'experimental mutagenicity'} <= set(reader.fieldnames or []):
            parser.error('Required input columns are missing')
        records = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in records):
        parser.error('Malformed CSV')
    pending = sorted(enumerate(records, 1),
                     key=lambda item: (not bool(item[1]['experimental mutagenicity'].strip()), item[0]))
    if args.experimental_only:
        pending = [(n, r) for n, r in pending if r['experimental mutagenicity'].strip()]
    if args.limit:
        pending = pending[:args.limit]
    directory = REPO/'models/toxtransformer'
    manifest = verify_manifest(directory, REPO/'artifacts/upstream-checkpoint.json')
    properties = load_properties(directory)
    signature = hashlib.sha256(json.dumps(dict(
        input_hash=hashlib.sha256(args.input.read_bytes()).hexdigest(),
        manifest=manifest, properties=properties, max_selfies=args.max_selfies,
        method='independent-structure-only-v1',
    ), sort_keys=True).encode()).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Prevent simultaneous runs from writing the same compound files.
    lock = args.output_dir/'.running.lock'
    try:
        lock_fd = lock.open('x')
    except FileExistsError:
        parser.error(f'Run lock exists: {lock}. Check for a running job before removing a stale lock.')
    lock_fd.write(str(os.getpid()) + '\n')
    lock_fd.close()
    try:
        torch.set_num_threads(1)
        model = load_checkpoint(directory, 'cpu').eval()
        assert len(properties) == model.tokenizer.num_assays
        save(args.output_dir/'catalog.json', properties)
        print(f'{len(pending)} compounds queued; {len(properties)} endpoints each; '
              'experimental mutagenicity labels first; context=0', flush=True)
        checked = False
        for position, (number, record) in enumerate(pending, 1):
            path = args.output_dir/f'compound_row_{number:04d}.json'
            data = dict(signature=signature,
                        n_context=0, max_selfies=args.max_selfies,
                        checkpoint_manifest=manifest, status='running', predictions=[])
            if path.exists():
                data = json.loads(path.read_text())
                if data.get('signature') != signature:
                    raise ValueError(f'Configuration/input changed: choose a new output directory: {path}')
                # Migrate old output files without recomputing predictions.
                if 'compound' in data or 'data_row' in data:
                    data.pop('compound', None)
                    data.pop('data_row', None)
                    save(path, data)
                if data['status'] in ('complete', 'unsupported'):
                    continue
            started = time.monotonic()
            try:
                encoded = encode_smiles(record['SMILES'].strip(), model.tokenizer, args.max_selfies)
                encoded = [v for v in encoded if v != model.token_pad_idx]
                if len(encoded)+2 > model.config.max_seq_len:
                    raise ValueError('Molecule exceeds total model sequence limit')
            except (ValueError, EncoderError, KeyError) as exc:
                data.update(status='unsupported', error=str(exc), predictions=[
                    {**p, 'probability': None} for p in properties])
                save(path, data)
                print(f'Row {number}: unsupported: {exc}', flush=True)
                continue
            if not checked:
                indices = [0, 2863, len(properties)-1]
                observed = batch_predict(model, encoded, indices)
                for index, value in zip(indices, observed):
                    reference = predict_checkpoint(model, record['SMILES'].strip(), index,
                                                   max_selfies=args.max_selfies)['probability']
                    if abs(value-reference) > 1e-5:
                        raise RuntimeError('Batched prediction differs from official helper')
                checked = True
                print('Batch/reference agreement passed (absolute tolerance 1e-5)', flush=True)
            done = len(data['predictions'])
            if [p['index'] for p in data['predictions']] != list(range(done)):
                raise ValueError(f'Invalid resume sequence: {path}')
            for begin in range(done, len(properties), args.batch_size):
                indices = list(range(begin, min(begin+args.batch_size, len(properties))))
                values = batch_predict(model, encoded, indices)
                data['predictions'].extend({**properties[i], 'probability': p}
                                           for i, p in zip(indices, values))
                if len(data['predictions']) // 256 != begin // 256 or len(data['predictions']) == len(properties):
                    save(path, data)
            data.update(status='complete', elapsed_seconds_this_attempt=time.monotonic()-started)
            save(path, data)
            print(f'{position}/{len(pending)}: row {number}, {record.get("name", "")}: '
                  f'{len(properties)} probabilities in {time.monotonic()-started:.1f}s', flush=True)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
