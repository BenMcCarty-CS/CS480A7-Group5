"""
Prepare the mined PR, comment/review and commit tables for analysis.

This script tidies and flags; it never drops anything. Each row keeps the
columns we need, plus a data_flags column noting anything wrong with it, so
the analysis can decide later what to exclude. Results go to
outputs/cleaned_full/ along with a short cleaning_report.txt.
"""

import csv
import lzma
from pathlib import Path
from tempfile import TemporaryDirectory

# Paths are relative to this script, so it can be run from any folder.
HERE = Path(__file__).resolve().parent

PR_FILE = HERE / "csv_data/full/PRs.csv.xz"
COMMENT_FILE = HERE / "csv_data/full/Comments.csv.xz"
COMMIT_FILE = HERE / "csv_data/full/Commits.csv.xz"
OUTPUT_DIR = HERE / "outputs/cleaned_full"

# PR bodies and the nested JSON cells (user, labels, base, ...) can be much
# longer than the csv module's default limit of 131,072 characters.
csv.field_size_limit(10_000_000)

PR_COLUMNS = [
    "number", "title", "body", "user", "state", "draft", "merged",
    "created_at", "updated_at", "closed_at", "merged_at",
    "additions", "deletions", "changed_files", "commits",
    "comments", "review_comments", "labels", "base",
    "author_association", "merge_commit_sha", "html_url",
]

# Issue comments, inline review comments and reviews share one file and
# are told apart by comment_type.
COMMENT_COLUMNS = [
    "pr_number", "comment_type", "id", "user", "body", "state",
    "created_at", "submitted_at", "updated_at", "author_association",
    "html_url", "commit_id", "original_commit_id",
    "pull_request_review_id", "in_reply_to_id", "path", "diff_hunk",
    "line", "original_line", "start_line", "original_start_line",
    "side", "start_side", "subject_type", "performed_via_github_app",
]

COMMIT_COLUMNS = [
    "pr_number", "sha", "commit", "author", "committer",
    "parents", "html_url",
]

ACTIVITY_TYPES = {"issue_comment", "review_comment", "review"}


def open_csv(path):
    """Open a CSV for reading, whether or not it's xz-compressed."""
    if path.suffix == ".xz":
        return lzma.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open(encoding="utf-8-sig", newline="")


def read_rows(path, needed_columns):
    """
    Yield each row of a CSV as a dict.

    Stops with an error if the header is empty, has a repeated name, or is
    missing a column we need, or if any row has the wrong number of fields.
    A broken file should halt the run, not quietly produce a shorter table.
    """
    with open_csv(path) as f:
        reader = csv.DictReader(f, strict=True)
        header = reader.fieldnames

        if not header:
            raise ValueError(f"No column headings in {path}")
        if len(header) != len(set(header)):
            raise ValueError(f"Repeated column headings in {path}")
        for column in needed_columns:
            if column not in header:
                raise ValueError(f"{path} is missing column: {column}")

        for row in reader:
            # DictReader puts surplus fields under a None key and pads short
            # rows with None values, so either one means the row is broken.
            if None in row or None in row.values():
                raise ValueError(
                    f"{path}: wrong number of fields near line {reader.line_num}"
                )
            yield row


def lines_changed(pr):
    """additions + deletions, or None if either is missing, non-numeric or negative."""
    try:
        additions = int(pr["additions"])
        deletions = int(pr["deletions"])
    except ValueError:
        return None

    if additions < 0 or deletions < 0:
        return None
    return additions + deletions


def clean_table(source, destination, columns, kind, known_prs):
    """
    Copy the chosen columns from source to destination and add data_flags
    (and lines_changed, for PRs). Returns a one-line summary for the report.

    kind is "PR", "Comment/review" or "Commit". The PR table has to be done
    first, because it fills known_prs, which the other two are checked against.
    """
    out_columns = list(columns)
    if kind == "PR":
        out_columns.append("lines_changed")
    out_columns.append("data_flags")

    written = 0
    flagged = 0
    seen_keys = set()

    with destination.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=out_columns)
        writer.writeheader()

        for row in read_rows(source, columns):
            cleaned = {column: row[column] for column in columns}
            flags = []

            if kind == "PR":
                pr_number = row["number"].strip()
                record_id = pr_number
                key = (pr_number,)
                if pr_number:
                    known_prs.add(pr_number)

                size = lines_changed(row)
                if size is None:
                    cleaned["lines_changed"] = ""
                    flags.append("missing_or_invalid_change_size")
                else:
                    cleaned["lines_changed"] = size

            else:
                pr_number = row["pr_number"].strip()
                if pr_number and pr_number not in known_prs:
                    flags.append("pr_not_in_pr_file")

                if kind == "Comment/review":
                    activity = row["comment_type"].strip()
                    record_id = row["id"].strip()
                    # The three activity types come from different GitHub
                    # endpoints, so the type is part of what makes a row unique.
                    key = (pr_number, activity, record_id)
                    if activity not in ACTIVITY_TYPES:
                        flags.append("unknown_activity_type")
                else:
                    record_id = row["sha"].strip()
                    key = (pr_number, record_id)

            if not pr_number:
                flags.append("missing_pr_number")
            if not record_id:
                flags.append("missing_record_id")

            # Duplicates stay in the table; every copy after the first is flagged.
            if pr_number and record_id:
                if key in seen_keys:
                    flags.append("repeated_record_key")
                seen_keys.add(key)

            cleaned["data_flags"] = ";".join(flags)
            writer.writerow(cleaned)

            written += 1
            if flags:
                flagged += 1
            if written % 100_000 == 0:
                print(kind, "records processed:", written)

    summary = f"{kind} records copied: {written}; records with flags: {flagged}"
    print(summary)
    return summary


def main():
    for path in (PR_FILE, COMMENT_FILE, COMMIT_FILE):
        if not path.is_file():
            raise FileNotFoundError(f"Cannot find input file: {path}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report = [
        "CSV PREPARATION REPORT",
        f"PR input: {PR_FILE}",
        f"Comment input: {COMMENT_FILE}",
        f"Commit input: {COMMIT_FILE}",
        "",
    ]
    known_prs = set()

    # Build everything in a scratch folder first and move it into place only
    # once all three tables are done. If the run fails partway, last run's
    # cleaned files are left as they were. The scratch folder sits inside
    # OUTPUT_DIR so the final moves are plain renames on the same disk.
    with TemporaryDirectory(dir=OUTPUT_DIR) as scratch:
        scratch = Path(scratch)

        report.append(clean_table(
            PR_FILE, scratch / "PRs_clean.csv", PR_COLUMNS, "PR", known_prs))
        report.append(clean_table(
            COMMENT_FILE, scratch / "Comments_clean.csv", COMMENT_COLUMNS,
            "Comment/review", known_prs))
        report.append(clean_table(
            COMMIT_FILE, scratch / "Commits_clean.csv", COMMIT_COLUMNS,
            "Commit", known_prs))

        report.extend([
            "",
            "All input records are retained. No study exclusions are applied.",
            "Original text, dates and selected nested cells are preserved.",
            "lines_changed = additions + deletions when both are valid nonnegative integers.",
            "Missing or invalid change sizes produce a blank result and a data flag.",
            "data_flags records basic issues; an empty flag is not proof of completeness.",
            "Repeated record keys are retained; occurrences after the first are flagged.",
            "For comments the key is PR number + activity type + ID.",
            "For commits the key is PR number + SHA; for PRs it is PR number.",
            "Collection completeness remains unverified.",
            "Substantive human feedback, review rounds and review duration are not calculated.",
            "Contributor experience and subsystem measures are not calculated.",
            "These are prepared tables, not the final analysis-ready research dataset.",
        ])
        (scratch / "cleaning_report.txt").write_text(
            "\n".join(report) + "\n", encoding="utf-8")

        for name in ("PRs_clean.csv", "Comments_clean.csv",
                     "Commits_clean.csv", "cleaning_report.txt"):
            (scratch / name).replace(OUTPUT_DIR / name)

    print("\nFinished. Files saved in:", OUTPUT_DIR)
    print("Check cleaning_report.txt and any nonblank data_flags before analysis.")


if __name__ == "__main__":
    main()