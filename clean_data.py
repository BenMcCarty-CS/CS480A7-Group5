import argparse
import csv
import json
from pathlib import Path


# Endpoint: (count field in PR details, record identifier)
ENDPOINTS = {
    "issue_comments": ("comments", "id"),
    "review_comments": ("review_comments", "id"),
    "reviews": (None, "id"),
    "commits": ("commits", "sha"),
}


def audit_record(path):
    row = {
        "source_file": path.name,
        "collection_status": "unverified",
    }

    try:
        record = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        row["record_status"] = "unreadable"
        row["error"] = str(error)
        return row

    if not isinstance(record, dict) or not isinstance(record.get("pr"), dict):
        row["record_status"] = "invalid_pr_structure"
        return row

    pr = record["pr"]
    row["pr_number"] = pr.get("number")
    row["record_status"] = (
        "parsed" if type(pr.get("number")) is int else "invalid_pr_number"
    )

    for endpoint, (count_field, id_field) in ENDPOINTS.items():
        expected = pr.get(count_field) if count_field else None
        row[f"{endpoint}_expected"] = expected
        items = record.get(endpoint)

        if endpoint not in record:
            status = "missing_endpoint"

        elif not isinstance(items, list):
            status = "invalid_endpoint_type"

        else:
            row[f"{endpoint}_rows"] = len(items)

            ids = [
                item.get(id_field)
                for item in items
                if isinstance(item, dict)
            ]
            valid_ids = [
                value for value in ids
                if type(value) in (int, str) and str(value)
            ]

            unique_count = len(set(valid_ids))
            row[f"{endpoint}_unique"] = unique_count
            row[f"{endpoint}_duplicates"] = len(valid_ids) - unique_count
            row[f"{endpoint}_invalid_items"] = len(items) - len(valid_ids)

            if len(valid_ids) != len(items):
                status = "invalid_items_or_ids"
            elif count_field is None:
                status = "no_reference_count"
            elif type(expected) is not int or expected < 0:
                status = "invalid_reference_count"
            else:
                status = (
                    "count_match"
                    if unique_count == expected
                    else "count_mismatch"
                )

        row[f"{endpoint}_check"] = status

    return row


def main():
    parser = argparse.ArgumentParser(
        description="Audit raw PR records; no effort measures yet."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    paths = sorted(args.input_dir.glob("*.json"))
    if not paths:
        parser.error("No JSON files found in the input directory.")

    fields = [
        "source_file",
        "pr_number",
        "record_status",
        "collection_status",
        "error",
    ]
    for endpoint in ENDPOINTS:
        for suffix in (
            "expected",
            "rows",
            "unique",
            "duplicates",
            "invalid_items",
            "check",
        ):
            fields.append(f"{endpoint}_{suffix}")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()

        for path in paths:
            writer.writerow(audit_record(path))

    print(f"Audited {len(paths)} files. Report: {args.output}")
    print(
        "Collection completeness remains unverified; "
        "count matches are checks only."
    )


if __name__ == "__main__":
    main()