Mycotoxin data and ToxTransformer predictions

Last inspected: November 9, 2026.

This folder contains a MicotoXilico dataset and two sets of locally generated
ToxTransformer predictions. No model was trained or fine-tuned in this project.
All predictions used the released pretrained checkpoint and molecular structures
only. Experimental labels were retained for comparison or used to select records;
they were not supplied as prediction context.

Files and directories

File or directory | Contents
micotoxilico_OG.csv | Original imported data: 4,359 records and 14 columns. Preserve its values and row order.
micotoxilico.csv | Same 4,359 records and original 14 columns, plus 20 ToxTransformer probability columns named with the full endpoint titles: 34 columns total.
toxicity_property_matches.json | The 20 endpoints whose titles contain genotoxic, carcinogenic, or mutagenic, ignoring case. Includes index, property ID, full title, source, and matching keywords.
experimental_mutagenicity/ | One compound JSON for each of the 305 records with a nonempty experimental mutagenicity label; each includes all 6,647 model properties.
experimental_mutagenicity/catalog.json | Full checkpoint property catalog, not a compound prediction file.
../Python scripts/ | Search and prediction scripts.
../Excecution tracker/ | Logs and metadata. The folder spelling is intentional here to match the existing directory.

There are 4,349 distinct CID values among the 4,359 records. Records have not been
deduplicated. Counts in this README refer to records, not necessarily unique
chemical structures.

Dataset source and download history

The source is the MicotoXilico website:

- Table: https://chemopredictionsuite.com/MicotoXilicoTable
- Page loader: https://chemopredictionsuite.com/static/MicotoXilico/script.js
- CSV used by that page: https://chemopredictionsuite.com/static/MicotoXilico/mycotoxins_tmap_final.csv

On November 4, 2026, the underlying CSV was downloaded directly from its publicly
accessible URL without logging in. The page loader fetched that CSV but displayed
only its first 300 records (data.slice(0, 300)). The downloaded file contained
4,359 records. This establishes the contents of that file, not that it necessarily
contains every record held by the maintainers.

The source used semicolon separators. It was converted to comma-separated UTF-8
CSV, preserving headers, values, empty cells, and row order; conversion equality
was checked. The local original was subsequently named micotoxilico_OG.csv.

The site directs users to register/request access for the full table. Direct URL
accessibility should not be treated as confirmation of the maintainers' intended
access terms. Registration/permission confirmation was discussed; this folder does
not document that it has been obtained. The website specifies non-commercial
academic use and requests citation:

Tolosa et al. MicotoXilico: An Interactive Database to Predict Mutagenicity,
Genotoxicity, and Carcinogenicity of Mycotoxins. *Toxins* 2023, 15, 355.
https://doi.org/10.3390/toxins15060355

Original CSV SHA-256 at verification:

5ee921a3c5c753ae2e54460af541cd105bf3a21c12fbb84fab3d6971a6223c89

Original column meanings

Columns | Meaning
name, cid, SMILES, category | Source chemical name, PubChem compound ID, molecular structure, and category.
experimental in vitro genotoxicity, experimental carcinogenicity, experimental mutagenicity | Experimental-result labels supplied by MicotoXilico. Empty cells mean no label supplied, not a negative result.
in vitro genotoxicity prediction, in vivo genotoxicity prediction, carcinogenicity prediction, mutagenicity prediction | Predictions already present in the source dataset. These are not our ToxTransformer predictions.
mutagenicity CoC ALERTS, mutagenicity Rb alerts | Source alert fields, preserved as provided; their detailed definitions require the source documentation.
index | Source dataset record index. It is not a ToxTransformer endpoint index.

Experimental mutagenicity coverage: 93 Mutagenic, 212 Non-mutagenic, and
4,054 unlabeled records. Both positive and negative labeled records were selected
for the all-property run.

Model and prediction method

Repository: https://github.com/toxindex/toxtransformer-research

- Released model version 2.1; 59,218,946 parameters; 16 transformer layers.
- 6,647 binary endpoints, indexed 0 through 6,646.
- Checkpoint SHA-256:
  8cae8b6490635e760a4dc00a66fb2626d8b3b8c1fba97fb7e0daee2935deeb1b.
- Artifact checksums were verified against the repository manifest.
- Inference runs locally on CPU, with one PyTorch thread and evaluation mode.
  No internet prediction service is called.
- The helper canonicalizes SMILES using RDKit while preserving stereochemistry,
  then encodes SELFIES. No salt stripping or tautomer harmonization was added.
- Molecular padding is removed before querying properties; n_context = 0.
- The molecular token limit was raised from 120 to 512. Structures are not
  truncated. This allows longer inputs but does not validate accuracy for them.

Each probability is the model's probability of class 1 for that specific
endpoint. It is not a universal toxicity probability, a confidence score, or a
probability of human disease. The original assay definitions and label-conversion
rules are needed to interpret class 1 scientifically.

The property source field (for example, ice or pubchem) is catalog attribution;
the model computes probabilities locally rather than retrieving assay measurements.
There are 1,670 properties with missing titles (null), which remain included.

Workflow 1: selected endpoints for all records

search_properties.py searched all catalog titles for three substrings:
genotoxic, carcinogenic, and mutagenic. It found 20 distinct endpoints:
12, 6, and 4 keyword matches respectively; two titles match more than one keyword.
These are title matches, not verified classifications of assay type.

predict_all_endpoints.py read micotoxilico_OG.csv, queried each selected endpoint
independently, and wrote micotoxilico.csv. Its added columns use the exact titles
listed in toxicity_property_matches.json. Every original cell was preserved.

- Initial 120-token run: 81,780 probabilities and 5,400 failed cells.
- Updated 512-token run: 87,160 probabilities and 20 failed cells.
- The 269 length-related failures were resolved by the larger input allowance.
- Remaining failure: original data row 1794, CID 151790,
  Uridine, 5-(bromo-80Br)-2'-deoxy-. Its [80Br] token is absent from the model
  vocabulary. All 20 added probability cells for that record are blank.

Error details and run settings are in the date-based micotox_errors_YYYYMMDD.json
and micotox_run_YYYYMMDD.json files under ../Excecution tracker/.

Workflow 2: all properties for experimentally labeled records

predict_all_properties_json.py --experimental-only selects the 305 rows with
nonempty experimental mutagenicity. It predicts every property independently,
using batches of 16 single-endpoint queries. It does not feed previous predictions
or experimental labels into later queries. Batched outputs were compared with the
official single-property helper for indices 0, 2863, and 6646, with an absolute
tolerance of 1e-5.

Verified status on November 9, 2026:

- 304 complete compound files, each with 6,647 finite probabilities between 0 and 1.
- 2,020,688 successful probability values in total.
- 1 unsupported compound file, compound_row_1794.json, containing an error
  for [80Br] and 6,647 null probabilities.
- All 305 selected source rows are represented; no unlabeled rows are included.

Matching JSON files to chemicals

compound_row_0034.json corresponds to the 34th data record in
micotoxilico_OG.csv, excluding the header. In Python, this is row-list element 33.
It is Isoaltenuene, CID 180444. The filename number is neither a CID nor the source
dataset's index nor a model property index.

The JSON files deliberately omit the source compound block, labels, source
predictions, and data_row field. Keep the original CSV and its row order so
the filenames can always be mapped back to structures. Do not sort or replace the
original CSV while retaining these filenames as if their mapping were unchanged.

Each compound JSON contains:

- signature: hash of input contents and model/configuration information, used
  to prevent incompatible resume operations; not a chemical identifier.
- n_context, max_selfies, and checkpoint_manifest: inference settings and
  model artifact provenance.
- status: running, complete, or unsupported.
- predictions: entries with index, property_id, title, source, and
  probability. A null probability means unavailable, never negative.
- error: explanation for unsupported input, when applicable.
- elapsed_seconds_this_attempt: time for the latest attempt, when complete.
  For resumed files, it need not include time spent in earlier attempts.

Commands

Run from the project folder using the existing model environment:

cd /Users/pangu/Desktop/JHU/PhD/toxtransformer/mycotoxin

Refresh the selected endpoint catalog:

python3 "Python scripts/search_properties.py"

Regenerate the selected-endpoint CSV (backs up existing output; replaces same-day logs):

../toxtransformer-research/.venv/bin/python \
  "Python scripts/predict_all_endpoints.py" --overwrite

Run or resume all-property JSON predictions for labeled records only:

../toxtransformer-research/.venv/bin/python -u \
  "Python scripts/predict_all_properties_json.py" \
  --experimental-only --output-dir "Data/experimental_mutagenicity"

Keep --experimental-only: omitting it queues all 4,359 records. The script skips
completed and unsupported files and resumes partially saved files. Progress is
saved approximately every 256 properties, so interruption can require recomputing
work since the last save. Terminal progress prints after each completed compound.

Use Ctrl+C for a clean stop. Internet loss does not stop local inference; laptop
sleep pauses computation. After an abrupt termination, a stale .running.lock
may remain. Confirm no prediction process is using the folder before removing it.
Never run two writers against the same output directory.

Old background .log and .pid files may describe earlier sessions, not the current
Terminal process. Check JSON status and current Terminal output for run progress.

Interpretation and reproducibility limits

- Neither numerical reproduction nor successfully obtaining probabilities measures
  scientific predictive accuracy.
- Experimental labels and source-model predictions are different kinds of data.
  Use appropriate experimental labels when evaluating performance.
- These 20 keyword-selected endpoints are not interchangeable. A DNA-damage
  response, bacterial mutation, cell viability, and animal cancer outcome measure
  different things. Do not average them into one toxicity score without justification.
- The released repository does not provide a verified complete historical training
  chemical list or split assignment for these weights. Training overlap with this
  dataset is unknown; do not describe this as confirmed unseen-compound validation.
- Calibration and an applicability domain are not established by this workflow.
- Exclude unavailable predictions from prediction-based calculations explicitly;
  never convert blanks/nulls to zero. Preserve duplicate records unless a documented
  deduplication protocol is applied separately.

Further model documentation:
model card (https://github.com/toxindex/toxtransformer-research/blob/main/MODEL_CARD.md),
data contract (https://github.com/toxindex/toxtransformer-research/blob/main/docs/data.md),
local inference (https://github.com/toxindex/toxtransformer-research/blob/main/docs/local-reproduction.md).
