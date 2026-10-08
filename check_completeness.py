"""
Completeness checks for the cleaned PR tables.

Run from the repo folder, after clean_csv.py has finished:

    python check_completeness.py

Step 1  comment counts per PR vs what GitHub reported on the PR itself,
        plus merged PRs that have no reviews at all
Step 2  commit counts per PR, keeping PRs at GitHub's 250-commit cap separate
Step 3  total PR count vs a GitHub search over the same window

Steps 1 and 2 work offline. Step 3 makes one request to GitHub.
Every PR that doesn't match is listed in outputs/completeness/mismatches.csv.
"""

import csv
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLEANED_DIR = HERE / "outputs/cleaned_full"
REPORT_DIR = HERE / "outputs/completeness"

# The miner's window: created from 30 Sep 2021 00:00 UTC up to and
# including 30 Sep 2026 00:00 UTC.
WINDOW_START = "2021-09-30T00:00:00Z"
WINDOW_END = "2026-09-30T00:00:00Z"

# GitHub's /pulls/{n}/commits endpoint never returns more than this many.
COMMIT_CAP = 250

csv.field_size_limit(10_000_000)


def read_csv(name):
    """Stream rows from one of the cleaned tables, one at a time."""
    with open(CLEANED_DIR / name, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def as_int(value):
    try:
        return int(value)
    except ValueError:
        return None


def load_prs():
    """Just the PR fields these checks need, keyed by PR number."""
    prs = {}
    for row in read_csv("PRs_clean.csv"):
        prs[row["number"].strip()] = {
            "comments": as_int(row["comments"]),
            "review_comments": as_int(row["review_comments"]),
            "commits": as_int(row["commits"]),
            "created_at": row["created_at"].strip(),
            "merged": bool(row["merged_at"].strip()),
            "draft": row["draft"].strip().lower() == "true",
        }
    return prs


def compare_counts(prs, mined, field, label):
    """
    Compare one count GitHub stored on each PR with the rows we mined.
    Prints a summary and returns a mismatch row for every PR that differs.
    """
    expected_total = mined_total = 0
    matched = fewer = more = none_mined = unknown = 0
    mismatches = []

    for number, pr in prs.items():
        expected = pr[field]
        got = mined.get(number, 0)
        mined_total += got

        if expected is None:
            unknown += 1
            continue

        expected_total += expected
        if got == expected:
            matched += 1
            continue

        if got < expected:
            fewer += 1
            if got == 0:
                none_mined += 1
        else:
            more += 1
        mismatches.append([number, label, expected, got, got - expected])

    print(f"  {label}: GitHub reports {expected_total:,}, mined {mined_total:,}")
    print(f"    PRs that match:      {matched:,} of {len(prs):,}")
    print(f"    PRs with fewer:      {fewer:,}  (none mined at all: {none_mined:,})")
    print(f"    PRs with more:       {more:,}")
    if unknown:
        print(f"    PRs with no count on record: {unknown:,}")
    return mismatches


def step1_comments(prs):
    print("\nSTEP 1: comments and reviews")
    print("  Reading Comments_clean.csv (this can take a minute)...")

    by_type = {"issue_comment": Counter(), "review_comment": Counter(), "review": Counter()}
    for row in read_csv("Comments_clean.csv"):
        kind = row["comment_type"].strip()
        if kind in by_type:
            by_type[kind][row["pr_number"].strip()] += 1

    mismatches = []
    mismatches += compare_counts(prs, by_type["issue_comment"], "comments", "issue comments")
    mismatches += compare_counts(prs, by_type["review_comment"], "review_comments", "inline review comments")

    # GitHub keeps no review count on the PR, so there's nothing to compare
    # against directly. But Zephyr needs two approvals to merge, so a merged
    # PR with no reviews at all usually means the reviews call came back empty.
    reviews = by_type["review"]
    no_reviews = [n for n, pr in prs.items() if pr["merged"] and reviews[n] == 0]
    merged = sum(pr["merged"] for pr in prs.values())
    print(f"  reviews: {sum(reviews.values()):,} mined")
    print(f"    merged PRs with no reviews at all: {len(no_reviews):,} of {merged:,}")
    mismatches += [[n, "merged but no reviews", "", 0, ""] for n in no_reviews]

    return mismatches


def step2_commits(prs):
    print("\nSTEP 2: commits")

    mined = Counter(row["pr_number"].strip() for row in read_csv("Commits_clean.csv"))

    # PRs over the cap will always show exactly 250 mined. That's a known
    # GitHub limit, not a mining failure, so they're reported on their own.
    capped = {n for n, pr in prs.items()
              if (pr["commits"] or 0) > COMMIT_CAP and mined.get(n, 0) == COMMIT_CAP}
    others = {n: pr for n, pr in prs.items() if n not in capped}

    mismatches = compare_counts(others, mined, "commits", "commits")
    print(f"  PRs over the {COMMIT_CAP}-commit cap (only {COMMIT_CAP} retrievable): {len(capped):,}")
    for n in sorted(capped, key=int):
        print(f"    #{n}: {prs[n]['commits']:,} commits on GitHub")
        mismatches.append([n, "commits over cap", prs[n]["commits"], COMMIT_CAP,
                           COMMIT_CAP - prs[n]["commits"]])
    return mismatches


def step3_total(prs):
    print("\nSTEP 3: total PR count")

    created = sorted(pr["created_at"] for pr in prs.values())
    outside = sum(1 for c in created if not WINDOW_START <= c <= WINDOW_END)
    drafts = sum(pr["draft"] for pr in prs.values())
    print(f"  PRs in the cleaned table: {len(prs):,}")
    print(f"    earliest created_at: {created[0]}")
    print(f"    latest created_at:   {created[-1]}")
    print(f"    outside the window:  {outside:,}")
    print(f"    marked as draft:     {drafts:,}")

    start = WINDOW_START.replace("Z", "+00:00")
    end = WINDOW_END.replace("Z", "+00:00")
    query = (f"repo:zephyrproject-rtos/zephyr is:pr is:closed draft:false "
             f"created:{start}..{end}")
    url = "https://api.github.com/search/issues?" + urllib.parse.urlencode(
        {"q": query, "per_page": 1})
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "cs480a7-completeness-check",
    })

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as e:
        print(f"  GitHub refused the search ({e.code}): {e.read().decode(errors='replace')[:300]}")
        print_browser_fallback()
        return
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  Couldn't reach GitHub: {e}")
        print_browser_fallback()
        return

    found = result["total_count"]
    print(f"  GitHub search today:      {found:,}")
    print(f"  GitHub minus mined:       {found - len(prs):+,}")
    if result.get("incomplete_results"):
        print("  GitHub marked this count as incomplete. Run the script again.")


def print_browser_fallback():
    query = ("is:pr is:closed draft:false "
             "created:2021-09-30..2026-09-29")
    link = ("https://github.com/zephyrproject-rtos/zephyr/pulls?"
            + urllib.parse.urlencode({"q": query}))
    print("  Open this instead and read the 'Closed' count above the list:")
    print(f"  {link}")
    print("  (Whole days only, so it can miss PRs opened at exactly 00:00 on 30 Sep 2026.)")


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading PRs_clean.csv...")
    prs = load_prs()

    mismatches = step1_comments(prs) + step2_commits(prs)
    step3_total(prs)

    out_file = REPORT_DIR / "mismatches.csv"
    with open(out_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["pr_number", "check", "github_count", "mined_count", "mined_minus_github"])
        writer.writerows(sorted(mismatches, key=lambda m: (m[1], int(m[0]))))

    print(f"\n{len(mismatches):,} mismatch rows written to {out_file}")


if __name__ == "__main__":
    main()