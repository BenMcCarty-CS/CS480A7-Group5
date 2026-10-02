from datetime import datetime as dt
import csv
import json
import os


# Maps the key each comment list is stored under to the comment_type written in Comments.csv.
COMMENT_TYPES = {
    "issue_comments": "issue_comment",
    "review_comments": "review_comment",
    "reviews": "review",
}


def parseISODatetime(dateString):
    if not dateString:
        return None
    return dt.fromisoformat(dateString.replace("Z", "+00:00"))


def loadRecords(rawDataDir):
    fileNames = [name for name in os.listdir(rawDataDir) if name.endswith(".json")]
    fileNames.sort(key=lambda name: int(name.removesuffix(".json")))

    records = []
    for fileName in fileNames:
        with open(os.path.join(rawDataDir, fileName), encoding="utf-8") as f:
            records.append(json.load(f))
    return records


def flattenRow(item):
    row = {}
    for key, value in item.items():
        if isinstance(value, (dict, list)):
            row[key] = json.dumps(value)
        elif value is None:
            row[key] = ""
        else:
            row[key] = value
    return row


def writeCSV(outputFileName, rows):
    if not rows:
        print(f"No rows to write to {outputFileName}, skipping it.")
        return

    # Different comment types have different fields, so the header is every key seen across all rows.
    fields = list(dict.fromkeys(key for row in rows for key in row))

    with open(outputFileName, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_MINIMAL, restval="")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {outputFileName}")


def makeCSV(rawDataDir):

    prRows = []
    commentRows = []
    commitRows = []

    for record in loadRecords(rawDataDir):
        number = record["pr"]["number"]
        prRows.append(flattenRow(record["pr"]))

        for key, commentType in COMMENT_TYPES.items():
            for comment in record[key]:
                commentRows.append({"pr_number": number, "comment_type": commentType, **flattenRow(comment)})

        for commit in record["commits"]:
            commitRows.append({"pr_number": number, **flattenRow(commit)})

    writeCSV("PRs.csv", prRows)
    writeCSV("Comments.csv", commentRows)
    writeCSV("Commits.csv", commitRows)
