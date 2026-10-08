import argparse
import csv
import json
from pathlib import Path


KNOWN_BOTS = {"zephyrbot"}
ACTIVITY_TYPES = ("issue_comments", "review_comments", "reviews")

FIELDS = [
    "source_file", "pr_number", "pr_author_id", "pr_created_at",
    "pr_closed_at", "pr_merged_at", "activity_type", "activity_id",
    "actor_id", "actor_login", "actor_type", "actor_class", "bot_reason",
    "is_pr_author", "created_at", "submitted_at", "updated_at",
    "review_state", "review_id", "reply_to_id", "commit_id", "path",
    "body", "collection_status",
]


def classify_actor(user):
    login = str(user.get("login") or "").lower()

    if user.get("type") == "Bot":
        return "automated", "account_type"
    if login.endswith("[bot]"):
        return "automated", "login_suffix"
    if login in KNOWN_BOTS:
        return "automated", "known_bot_list"
    if user.get("type") == "User":
        return "potential_human", ""

    return "unknown", ""


def activity_rows(path):
    record = json.loads(path.read_text(encoding="utf-8-sig"))
    pr = record["pr"]
    author_id = (pr.get("user") or {}).get("id")

    for activity_type in ACTIVITY_TYPES:
        items = record[activity_type]

        if not isinstance(items, list):
            raise ValueError(
                f"{path.name}: {activity_type} must be a list"
            )

        for item in items:
            user = item.get("user") or {}
            actor_class, reason = classify_actor(user)
            actor_id = user.get("id")

            is_author = (
                actor_id == author_id
                if actor_id is not None and author_id is not None
                else None
            )

            yield {
                "source_file": path.name,
                "pr_number": pr["number"],
                "pr_author_id": author_id,
                "pr_created_at": pr.get("created_at"),
                "pr_closed_at": pr.get("closed_at"),
                "pr_merged_at": pr.get("merged_at"),
                "activity_type": activity_type,
                "activity_id": item["id"],
                "actor_id": actor_id,
                "actor_login": user.get("login"),
                "actor_type": user.get("type"),
                "actor_class": actor_class,
                "bot_reason": reason,
                "is_pr_author": is_author,
                "created_at": item.get("created_at"),
                "submitted_at": item.get("submitted_at"),
                "updated_at": item.get("updated_at"),
                "review_state": item.get("state"),
                "review_id": item.get("pull_request_review_id"),
                "reply_to_id": item.get("in_reply_to_id"),
                "commit_id": item.get("commit_id"),
                "path": item.get("path"),
                "body": item.get("body"),
                "collection_status": "unverified",
            }


def main():
    parser = argparse.ArgumentParser(
        description="Export observed PR review activity."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    paths = sorted(args.input_dir.glob("*.json"))
    if not paths:
        parser.error("No JSON files found.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")

    count = 0
    with temporary.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()

        for path in paths:
            for row in activity_rows(path):
                writer.writerow(row)
                count += 1

    temporary.replace(args.output)

    print(
        f"Exported {count} activity records "
        f"from {len(paths)} PR files."
    )
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()