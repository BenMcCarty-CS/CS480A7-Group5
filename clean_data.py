import csv
import json
import sys
from datetime import datetime, timezone
from collections import defaultdict

csv.field_size_limit(sys.maxsize)

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



def clean_data(PRs: str, commits: str, comments: str):


    commitsDict = defaultdict(list)
    with open(commits, mode='r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            commitsDict[int(row['pr_number'])].append(dict(row))

    commentsDict = defaultdict(list)
    with open(comments, mode='r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                commentsDict[int(row['pr_number'])].append(dict(row))


    prsDict = {}
    with open(PRs, mode='r', encoding='utf-8') as f:
        for row in csv.DictReader(f):

            if row['state'].strip().lower() == 'open':
                 continue
            
            prNum = int(row['number'])

            isMerged = row.get('merged', '').strip().lower() == 'true' or bool(row.get('merged_at'))
            outcome = "merged" if isMerged else "closed"
            endTimeStr = row['merged_at'] if isMerged else row['closed_at']
            createdAt = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
            endAt = datetime.fromisoformat(endTimeStr.replace('Z', '+00:00'))
            timeSpentOpen = (endAt - createdAt).total_seconds() / 86400.0, 3


            additions = int(row['additions']) if row['additions'] else 0
            deletions = int(row['deletions']) if row['deletions'] else 0
            linesChanged = additions + deletions

            if linesChanged == 0:
                continue

            labelsJSON = json.loads(row['labels']) if row['labels'] else []
            labels = [label['name'] for label in labelsJSON]

            commentsList = commentsDict.get(prNum, [])
            commitsList = commitsDict.get(prNum, [])

            numComments = len(commentsList)
            numCommits = len(commitsList) if commitsList else (int(row['commits']) if row.get('commits') else 0)
            commitsPerComment = (numCommits / numComments, 3) if numComments > 0 else None

            prsDict[prNum] = {
                        "status": outcome,
                        "lines_changed": linesChanged,
                        "additions": additions,
                        "deletions": deletions,
                        "time_spent_open_days": timeSpentOpen,
                        "labels": labels,
                        "commits_per_comment": commitsPerComment
                    }        
            
    writeCSV("PR_Summary_Metrics.csv", list(prsDict.values()))          

    return
