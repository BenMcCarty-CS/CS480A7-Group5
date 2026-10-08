#!/usr/bin/env python3
"""Offline Zephyr PR preparation. Standard library only; no mining or Git writes."""


import argparse

import csv

import json

from pathlib import Path

ENDPOINTS = {'issue_comments': ('comments', 'id'), 'review_comments': ('review_comments', 'id'), 'reviews': (None, 'id'), 'commits': ('commits', 'sha')}

def audit_record(path):
    row = {'source_file': path.name, 'collection_status': 'unverified'}
    try:
        record = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        row['record_status'] = 'unreadable'
        row['error'] = str(error)
        return row
    if not isinstance(record, dict) or not isinstance(record.get('pr'), dict):
        row['record_status'] = 'invalid_pr_structure'
        return row
    pr = record['pr']
    row['pr_number'] = pr.get('number')
    row['record_status'] = 'parsed' if type(pr.get('number')) is int else 'invalid_pr_number'
    for endpoint, (count_field, id_field) in ENDPOINTS.items():
        expected = pr.get(count_field) if count_field else None
        row[f'{endpoint}_expected'] = expected
        items = record.get(endpoint)
        if endpoint not in record:
            status = 'missing_endpoint'
        elif not isinstance(items, list):
            status = 'invalid_endpoint_type'
        else:
            row[f'{endpoint}_rows'] = len(items)
            ids = [item.get(id_field) for item in items if isinstance(item, dict)]
            valid_ids = [v for v in ids if type(v) in (int, str) and str(v)]
            unique_count = len(set(valid_ids))
            row[f'{endpoint}_unique'] = unique_count
            row[f'{endpoint}_duplicates'] = len(valid_ids) - unique_count
            row[f'{endpoint}_invalid_items'] = len(items) - len(valid_ids)
            if len(valid_ids) != len(items):
                status = 'invalid_items_or_ids'
            elif count_field is None:
                status = 'no_reference_count'
            elif type(expected) is not int or expected < 0:
                status = 'invalid_reference_count'
            else:
                status = 'count_match' if unique_count == expected else 'count_mismatch'
        row[f'{endpoint}_check'] = status
    return row


def scan_inventory(path, sample_numbers):
    """Read a large CSV incrementally; retain only PR identifiers and counters."""
    from collections import Counter
    from datetime import datetime, timezone
    seen = set()
    counts = Counter()
    states, drafts, years = Counter(), Counter(), Counter()
    earliest = latest = None
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, strict=True)
        header = next(reader)
        if len(header) != len(set(header)):
            raise ValueError("Inventory CSV has duplicate column names")
        index = {name: header.index(name) for name in ("number", "created_at", "state", "draft")}
        for row in reader:
            counts["rows"] += 1
            if counts["rows"] % 10000 == 0:
                print(f"CSV: {counts['rows']:,} records read...", flush=True)
            if len(row) != len(header):
                counts["wrong_field_count"] += 1
                continue
            number = row[index["number"]].strip()
            if not number:
                counts["missing_pr_number"] += 1
            elif number in seen:
                counts["duplicate_pr_rows"] += 1
            else:
                seen.add(number)
            states[row[index["state"]] or "<blank>"] += 1
            drafts[row[index["draft"]] or "<blank>"] += 1
            try:
                created = datetime.fromisoformat(row[index["created_at"]].replace("Z", "+00:00"))
                if created.tzinfo is None:
                    raise ValueError("Timestamp has no timezone")
                created = created.astimezone(timezone.utc)
            except ValueError:
                counts["invalid_created_at"] += 1
                continue
            years[created.year] += 1
            earliest = created if earliest is None else min(earliest, created)
            latest = created if latest is None else max(latest, created)
    return {
        "path": str(path.resolve()), "size_bytes": path.stat().st_size,
        "counts": {key: counts[key] for key in ("rows", "wrong_field_count", "missing_pr_number", "duplicate_pr_rows", "invalid_created_at")},
        "unique_pr_numbers": len(seen), "states": dict(states), "drafts": dict(drafts),
        "creation_years": dict(sorted(years.items())),
        "earliest_creation": earliest.isoformat() if earliest else None,
        "latest_creation": latest.isoformat() if latest else None,
        "raw_pr_numbers_absent_from_csv": sorted(str(n) for n in sample_numbers if str(n) not in seen),
        "provenance_note": "Matching PR numbers do not prove both sources came from the same collection run.",
    }


def run_pipeline():
    import hashlib
    import shlex
    import sys
    from collections import Counter
    from contextlib import ExitStack
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--pr-csv", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/preparation"))
    args = parser.parse_args()
    csv.field_size_limit(sys.maxsize)
    paths = sorted(args.raw_dir.glob("*.json"))
    if not paths:
        parser.error("No JSON files found. Use --raw-dir sample_data for the five samples.")
    if args.pr_csv and not args.pr_csv.is_file():
        parser.error(f"CSV file not found: {args.pr_csv}")
    # Each run gets a new directory; earlier outputs and annotations are preserved.
    run_dir = args.output_dir / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    summary = {"analysis_ready": False, "source_json_files": len(paths), "prepared_prs": 0,
               "activity_records": 0, "failed_json_files": 0, "failure_details": [],
               "activity_types": Counter(), "raw_sources": [], "collection_status": "unverified"}
    audit_fields = ["source_file", "pr_number", "record_status", "collection_status", "error"]
    for endpoint in ENDPOINTS:
        audit_fields.extend(f"{endpoint}_{suffix}" for suffix in ("expected", "rows", "unique", "duplicates", "invalid_items", "check"))
    sample_numbers = set()
    with ExitStack() as stack:
        def writer(name, fields):
            file = stack.enter_context((run_dir / name).open("w", encoding="utf-8", newline=""))
            result = csv.DictWriter(file, fieldnames=fields)
            result.writeheader()
            return result
        audit_writer = writer("data_quality.csv", audit_fields)
        activity_writer = writer("activity.csv", FIELDS)
        validation_writer = writer("manual_review.csv", FIELDS + ["manual_label", "manual_reason", "coder"])
        pr_writer = None
        for path in paths:
            audit = audit_record(path)
            audit_writer.writerow(audit)
            try:
                summary["raw_sources"].append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
                pr_row = prepare_row(path)
                # Hold one PR's activities to avoid partially writing a malformed PR.
                activities = list(activity_rows(path))
                if pr_row["pr_number"] in sample_numbers:
                    raise ValueError("PR number already appeared in another JSON file")
                for item in activities:
                    if not isinstance(item["body"], (str, type(None))):
                        raise ValueError("Activity body must be text or null")
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
                summary["failed_json_files"] += 1
                summary["failure_details"].append({"file": path.name, "error": str(error)})
                continue
            if pr_writer is None:
                pr_writer = writer("pr_preparation.csv", list(pr_row))
            pr_writer.writerow(pr_row)
            sample_numbers.add(pr_row["pr_number"])
            summary["prepared_prs"] += 1
            for item in activities:
                activity_writer.writerow(item)
                validation_writer.writerow(item)
                summary["activity_records"] += 1
                summary["activity_types"][item["activity_type"]] += 1
    if summary["prepared_prs"] == 0:
        (run_dir / "pr_preparation.csv").write_text("pr_number,measurement_status\n", encoding="utf-8")
    summary["command"] = shlex.join([sys.executable] + sys.argv)
    summary["python_version"] = sys.version
    summary["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    summary["processing_finished_at"] = datetime.now(timezone.utc).isoformat()
    summary["timestamp_note"] = "Processing time is not the GitHub collection time. Source fetch timestamps are unavailable."
    if args.pr_csv:
        print("Scanning PR CSV without loading the entire file...", flush=True)
        summary["inventory"] = scan_inventory(args.pr_csv, sample_numbers)
    summary["activity_types"] = dict(summary["activity_types"])
    (run_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = f"""ZEPHYR DATA PREPARATION - DEVELOPMENT OUTPUT

STATUS: NOT ANALYSIS-READY

Reproduce with Python 3.12; no third-party packages required:
{summary['command']}

Local JSON artifacts found: {len(paths)}
PR rows prepared: {summary['prepared_prs']}
JSON files not prepared: {summary['failed_json_files']}
Activity records exported: {summary['activity_records']}
Observation-period filtering: NOT APPLIED
Study exclusions: NOT APPLIED
Final analysis-ready observations: NOT PRODUCED

FILES
data_quality.csv: endpoint count and schema checks for every JSON input.
activity.csv: raw observed comments and reviews, including authors and bots.
pr_preparation.csv: PR characteristics and provisional observed activity counts.
manual_review.csv: activity plus blank manual_label, manual_reason and coder fields.
run_summary.json: configuration, input hashes, counts, failures and optional CSV coverage.

DEFINITIONS AND LIMITS
All activity counts cover collected activity without a study cutoff or merge-time filter.
Candidate text records are NOT substantive review comments; they may include LGTM,
administrative messages, and post-merge discussion. Potential humans are not validated.
Author contributions and likely bot activity are flagged, not erased from activity.csv.
Known automated login: zephyrbot. Also flag Bot accounts and [bot] login suffixes.
PR characteristics describe retrieval-time values, not necessarily opening-time values.
Substantive comments, rounds, review duration, prior experience and subsystem count
remain blank because their required definitions, source data or validation are unfinished.
Blank outcomes mean unavailable; they do not mean zero.
Reviews have no reference total. Count matches do not certify collection completeness.
The raw JSON files remain authoritative for nulls, nesting and source details.
In PR summaries, repeated activity IDs within each type are counted once; activity.csv
retains all rows. Audit duplicate flags must be reviewed for conflicting duplicates.
This run processes supplied JSON records only. An inventory CSV does not supply
missing conversations. Matching identifiers do not establish common collection provenance.

NEXT REQUIREMENTS FOR THE STUDY
Obtain the full activity collection corresponding to the study PRs.
Obtain changed-file paths and historical contributor inventory.
Finalize population, activity cutoff, substantive-comment, round and duration rules.
Resolve missing collection provenance and endpoint-completeness evidence.
Validate derived measures and classifications with human inspection.
Run on full data, apply documented filters, and report the actual exclusion funnel.
Complete the research design and final replication package.

MANUAL REVIEW (development sheet, not a representative validation sample)
S: substantive reviewer feedback; N: non-substantive; A: PR-author contribution;
B: automated; U: uncertain. These labels are working categories, not final labels.
Do not treat assistant-provided examples as independent human agreement evidence.
"""
    (run_dir / "README.txt").write_text(report, encoding="utf-8")
    print(f"DONE: {summary['prepared_prs']} PRs; {summary['activity_records']} activity records; {summary['failed_json_files']} files not prepared.")
    print(f"Outputs: {run_dir.resolve()}")
    print("Preparation complete. Research outcomes remain unfinished; see README.txt.")
    if summary["failed_json_files"]:
        print("Some records failed. Inspect run_summary.json before using any output.")



import argparse

import csv

import json

from pathlib import Path

KNOWN_BOTS = {'zephyrbot'}

ACTIVITY_TYPES = ('issue_comments', 'review_comments', 'reviews')

FIELDS = ['source_file', 'pr_number', 'pr_author_id', 'pr_created_at', 'pr_closed_at', 'pr_merged_at', 'activity_type', 'activity_id', 'actor_id', 'actor_login', 'actor_type', 'actor_class', 'bot_reason', 'is_pr_author', 'created_at', 'submitted_at', 'updated_at', 'review_state', 'review_id', 'reply_to_id', 'commit_id', 'path', 'body', 'collection_status']

def classify_actor(user):
    login = str(user.get('login') or '').lower()
    if user.get('type') == 'Bot':
        return ('automated', 'account_type')
    if login.endswith('[bot]'):
        return ('automated', 'login_suffix')
    if login in KNOWN_BOTS:
        return ('automated', 'known_bot_list')
    if user.get('type') == 'User':
        return ('potential_human', '')
    return ('unknown', '')

def activity_rows(path):
    record = json.loads(path.read_text(encoding='utf-8-sig'))
    pr = record['pr']
    author_id = (pr.get('user') or {}).get('id')
    for activity_type in ACTIVITY_TYPES:
        items = record[activity_type]
        if not isinstance(items, list):
            raise ValueError(f'{path.name}: {activity_type} must be a list')
        for item in items:
            user = item.get('user') or {}
            actor_class, reason = classify_actor(user)
            actor_id = user.get('id')
            is_author = actor_id == author_id if actor_id is not None and author_id is not None else None
            yield {'source_file': path.name, 'pr_number': pr['number'], 'pr_author_id': author_id, 'pr_created_at': pr.get('created_at'), 'pr_closed_at': pr.get('closed_at'), 'pr_merged_at': pr.get('merged_at'), 'activity_type': activity_type, 'activity_id': item['id'], 'actor_id': actor_id, 'actor_login': user.get('login'), 'actor_type': user.get('type'), 'actor_class': actor_class, 'bot_reason': reason, 'is_pr_author': is_author, 'created_at': item.get('created_at'), 'submitted_at': item.get('submitted_at'), 'updated_at': item.get('updated_at'), 'review_state': item.get('state'), 'review_id': item.get('pull_request_review_id'), 'reply_to_id': item.get('in_reply_to_id'), 'commit_id': item.get('commit_id'), 'path': item.get('path'), 'body': item.get('body'), 'collection_status': 'unverified'}

import argparse

import csv

import json

from pathlib import Path

def prepare_row(path):
    audit = audit_record(path)
    if audit.get('record_status') != 'parsed':
        raise ValueError(f'{path.name}: PR record failed the audit')
    for endpoint in ('issue_comments', 'review_comments', 'reviews', 'commits'):
        if audit[f'{endpoint}_check'] not in ('count_match', 'count_mismatch', 'no_reference_count'):
            raise ValueError(f'{path.name}: invalid {endpoint}; inspect the audit')
    record = json.loads(path.read_text(encoding='utf-8-sig'))
    pr = record['pr']
    user = pr.get('user') or {}
    activities = {}
    for item in activity_rows(path):
        activities[item['activity_type'], item['activity_id']] = item
    candidates = [item for item in activities.values() if item['actor_class'] == 'potential_human' and item['is_pr_author'] is False]
    additions, deletions = (pr.get('additions'), pr.get('deletions'))
    size = additions + deletions if type(additions) is int and type(deletions) is int and (additions >= 0) and (deletions >= 0) else None
    row = {'pr_number': pr['number'], 'source_file': path.name, 'title': pr.get('title'), 'author_id': user.get('id'), 'author_login': user.get('login'), 'created_at': pr.get('created_at'), 'closed_at': pr.get('closed_at'), 'merged_at': pr.get('merged_at'), 'state_at_retrieval': pr.get('state'), 'draft_at_retrieval': pr.get('draft'), 'base_branch_at_retrieval': (pr.get('base') or {}).get('ref'), 'additions_at_retrieval': additions, 'deletions_at_retrieval': deletions, 'lines_changed_at_retrieval': size, 'changed_files_at_retrieval': pr.get('changed_files'), 'observed_unique_activity_records': len(activities), 'observed_automated_activity_records': sum((item['actor_class'] == 'automated' for item in activities.values())), 'observed_author_activity_records': sum((item['is_pr_author'] is True for item in activities.values())), 'observed_potential_reviewer_accounts': len({item['actor_id'] for item in candidates if item['actor_id'] is not None}), 'observed_candidate_text_records': sum((bool((item['body'] or '').strip()) for item in candidates)), 'activity_scope': 'all_collected_times_no_cutoff_filter', 'collection_status': 'unverified', 'substantive_review_comments': None, 'review_rounds': None, 'review_duration_hours': None, 'prior_contributor_experience': None, 'subsystem_count': None, 'measurement_status': 'unfinished_requires_definitions_data_and_validation'}
    for endpoint in ('issue_comments', 'review_comments', 'reviews', 'commits'):
        for suffix in ('unique', 'duplicates', 'check'):
            row[f'{endpoint}_{suffix}'] = audit[f'{endpoint}_{suffix}']
    return row


if __name__ == "__main__":
    run_pipeline()
