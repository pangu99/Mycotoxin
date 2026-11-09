EXPERIMENTAL MUTAGENICITY: ALL-PROPERTY TOXTRANSFORMER PREDICTIONS
Last verified: November 9, 2026

PURPOSE

This folder contains ToxTransformer predictions for the 305 records in
../micotoxilico_OG.csv that have a nonempty "experimental mutagenicity" label:
93 Mutagenic and 212 Non-mutagenic records.

Experimental mutagenicity was used ONLY to select records. Each selected
structure was queried against ALL 6,647 model properties. 

CONTENTS AND FINAL STATUS

- compound_row_NNNN.json: one output file per selected original CSV record.
- catalog.json: the complete model property catalog, not a compound result.
- README.txt: this documentation.

Verified results:
- 305 compound JSON files.
- 304 files with status "complete", each containing 6,647 probabilities.
- 2,020,688 successful probability values in total.
- 1 file with status "unsupported": compound_row_1794.json.
- No unlabeled source records are included.

HOW TO IDENTIFY A COMPOUND

The number in the filename is the one-based DATA ROW in ../micotoxilico_OG.csv,
excluding the header. For example:

compound_row_0034.json = data row 34 = Isoaltenuene, PubChem CID 180444.

In Python, this corresponds to element 33 of a list produced by csv.DictReader.
The filename number is not the source dataset's "index", a PubChem CID, or a
ToxTransformer property index.

The JSON files intentionally omit the original compound block, SMILES, source
labels, source predictions, and data_row field. To identify a result, use its
filename and the original CSV. Preserve that CSV's values and row order; sorting
it would break the filename-to-compound mapping.

Original CSV SHA-256:
5ee921a3c5c753ae2e54460af541cd105bf3a21c12fbb84fab3d6971a6223c89

JSON FIELDS

signature
  A hash of input contents and model/settings information used for safe resume.
  It is not a chemical identifier.

n_context
  0: predictions use molecular structure only, with no experimental assay labels
  or previous predictions supplied as context.

max_selfies
  512: the maximum molecular token count allowed by this run. Structures are not
  truncated. This extends the upstream helper's 120-token default and does not
  establish accuracy for larger molecules.

checkpoint_manifest
  Model version, artifact checksums, property-source counts, and other model
  provenance. These are checkpoint metadata, not compound-specific results.

status
  complete: all 6,647 endpoint probabilities are saved.
  running: a partial output; processing may be active or interrupted.
  unsupported: input could not be encoded; probabilities are null.

predictions
  One entry per property, with:
  - index: model endpoint number, from 0 through 6646.
  - property_id: stable catalog identifier for that endpoint.
  - title: catalog description; null if unavailable.
  - source: endpoint data-source attribution, such as ice, pubchem, or chembl.
  - probability: model probability of class 1 for that specific endpoint.

error
  Explanation of an unsupported input, when applicable.

elapsed_seconds_this_attempt
  Processing time for the latest attempt. For resumed files, this may omit
  computation done before an interruption and is not necessarily total runtime.

KNOWN FAILURE

compound_row_1794.json corresponds to:
  Name: Uridine, 5-(bromo-80Br)-2'-deoxy-
  PubChem CID: 151790
  Error: SELFIES tokens absent from training vocabulary: ['[80Br]']

The model vocabulary does not contain the bromine-80 isotope token. Increasing
the length limit cannot resolve it. No isotope substitution was performed.
All 6,647 probabilities for this record are null. Exclude this record from
prediction-based analyses and document the exclusion; never treat null as zero.

MODEL AND COMPUTATION

Repository: https://github.com/toxindex/toxtransformer-research
Model version: 2.1
Parameters: 59,218,946
Transformer layers: 16
Properties: 6,647 binary endpoints
Checkpoint SHA-256:
8cae8b6490635e760a4dc00a66fb2626d8b3b8c1fba97fb7e0daee2935deeb1b

The model and tokenizer artifacts were checked against the repository manifest.
The full pretrained model runs locally on CPU with one PyTorch thread. Internet
access is not required during prediction and compounds are not uploaded.

The helper canonicalizes SMILES with RDKit while preserving stereochemistry,
then encodes SELFIES. No additional salt removal or tautomer normalization was
introduced. Padding is removed before querying endpoints.

Properties are processed in batches of 16 independent single-endpoint queries.
One endpoint's predicted label is never fed into another endpoint's query.
Batched results were checked against the official single-property helper for
indices 0, 2863, and 6646 with absolute tolerance 1e-5. This checks computational
agreement, not scientific accuracy.

RUNNING OR RESUMING

Script: ../../Python scripts/predict_all_properties_json.py

Run these commands in Terminal:

cd /Users/pangu/Desktop/JHU/PhD/toxtransformer/mycotoxin

../toxtransformer-research/.venv/bin/python -u "Python scripts/predict_all_properties_json.py" --experimental-only --output-dir "Data/experimental_mutagenicity"

Keep --experimental-only to restrict processing to the 305 labeled records.
Without it, the script queues all 4,359 source records.

The script skips complete and unsupported files and resumes partial files.
It saves progress approximately every 256 properties and prints progress after
each completed compound. Use Ctrl+C to stop cleanly, then repeat the same command
to resume. Keep the JSON files; deleting them loses saved progress.

Internet disconnection does not interrupt local computation. Laptop sleep pauses
computation. An abrupt shutdown may leave a .running.lock file: confirm that no
prediction process is using this directory before removing a stale lock.
Do not start two prediction processes writing into this directory simultaneously.

INTERPRETING THE RESULTS

These are model predictions, not experimental measurements or database lookups.
The source field attributes the endpoint's data source; the model computes the
probability locally.

Class 1 has the meaning defined by each endpoint's original labeling rules.
Do not assume every endpoint means "toxic" or "mutagenic", and do not interpret
these probabilities as human disease risks or calibrated confidence estimates.
Original assay definitions and binary-label conversion rules require additional
source documentation.

The repository does not provide a verified complete historical training chemical
list or split assignments for these weights. Overlap with these compounds is
unknown; this is not confirmed validation on previously unseen compounds.

DATA PROVENANCE

The input originated from the MicotoXilico CSV used by its public table page:
https://chemopredictionsuite.com/MicotoXilicoTable
https://chemopredictionsuite.com/static/MicotoXilico/mycotoxins_tmap_final.csv

On November 4, 2026, that publicly accessible source file was downloaded directly
without login. It contained 4,359 records although the page displayed only 300.
Semicolon-separated source data was converted to comma-separated UTF-8 CSV,
preserving values and row order.

The site directs users to register/request full access and specifies non-commercial
academic use with citation. Direct URL accessibility does not confirm intended
permission; this folder does not document registration or permission approval.

Dataset citation:
Tolosa et al. MicotoXilico: An Interactive Database to Predict Mutagenicity,
Genotoxicity, and Carcinogenicity of Mycotoxins. Toxins 2023, 15, 355.
https://doi.org/10.3390/toxins15060355

For the broader project history and the separate 20-endpoint CSV workflow,
see ../README.txt.
