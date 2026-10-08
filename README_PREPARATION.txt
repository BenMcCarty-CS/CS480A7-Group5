ZEPHYR DATA PREPARATION

Requires Python 3.12. prepare_zephyr.py uses only the standard library.

From the repository root, run:
python prepare_zephyr.py --raw-dir sample_data --pr-csv /path/to/FinalRawData.csv --output-dir outputs/preparation

Replace the CSV path with its actual location.
Obtain the raw JSON files from the team's collection.
For the full collection, replace sample_data with its directory.

Each run creates a new output folder containing:
- data_quality.csv
- activity.csv
- pr_preparation.csv
- manual_review.csv
- run_summary.json
- README.txt

Raw inputs are preserved. Processing is offline.
Generated outputs and local samples are ignored by Git.

Verified development run:
5 PRs prepared; 75 activity records; 0 failed JSON files.
The supplied PR CSV contains 57,949 unique PR numbers.
All five sample PRs appear in that CSV.

STATUS: Development preparation pipeline, not an analysis-ready dataset.
Activity counts are provisional and have no observation-cutoff filter.
Research outcomes remain unavailable until definitions, collection
coverage and human validation are resolved.
See measurement_rules.md for the working measurement definitions.

The final replication package must separately include the required
raw CSVs, final analysis-ready CSV and complete reproduction instructions.
