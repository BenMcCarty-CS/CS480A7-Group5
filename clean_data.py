import csv
import json
import sys
from datetime import datetime, timezone
from collections import defaultdict
import ctypes

csv.field_size_limit(int(ctypes.c_ulong(-1).value // 2))

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
        totalPRs = 0
        totalCommitsPerComment = 0
        totalTimeOpen = 0
        for row in csv.DictReader(f):
            if row['state'].strip().lower() == 'open':
                 continue
            
            additions = int(row['additions']) if row['additions'] else 0
            deletions = int(row['deletions']) if row['deletions'] else 0
            filesChanged = int(row['changed_files']) if row['changed_files'] else 0
            linesChanged = additions + deletions

            if linesChanged == 0:
                continue

            userJSON = json.loads(row['user']) if row['user'] else []
            userName = userJSON["login"] if userJSON['login'] else "ANON"
            prNum = int(row['number'])
            print(f"Cleaning PR {prNum}...")

            isMerged = row.get('merged', '').strip().lower() == 'true' or bool(row.get('merged_at'))
            outcome = "merged" if isMerged else "closed"

            endTimeStr = row['merged_at'] if isMerged else row['closed_at']
            createdAt = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
            endAt = datetime.fromisoformat(endTimeStr.replace('Z', '+00:00'))
            if((endAt - createdAt).total_seconds() <= 30):
                continue
            timeSpentOpen = round((endAt - createdAt).total_seconds() / 86400.0, 3)
            
            

            labelsJSON = json.loads(row['labels']) if row['labels'] else []
            labels = [label['name'] for label in labelsJSON]

            commentsList = commentsDict.get(prNum, [])
            review_comments_number = int(row["review_comments"])
            commitsList = commitsDict.get(prNum, [])

            numComments = len(commentsList) + review_comments_number
            numCommits = len(commitsList) if commitsList else (int(row['commits']) if row.get('commits') else 0)
            if(numComments == 0 or numCommits == 0):
                continue
            commitsPerComment = round(numCommits / numComments, 3) if numComments > 0 else None

            prsDict[prNum] = {
                        "status": outcome,
                        "lines_changed": linesChanged,
                        "additions": additions,
                        "deletions": deletions,
                        "time_spent_open_days": timeSpentOpen,
                        "labels": labels,
                        "commits_per_comment": commitsPerComment,
                        "committer" : userName,
                        'changed_files': filesChanged
                    }
            
            totalPRs += 1
            totalTimeOpen += timeSpentOpen
            totalCommitsPerComment += commitsPerComment

        averageTimeSpentOpen = totalTimeOpen/totalPRs
        averageCommitsPerComment = totalCommitsPerComment/totalPRs
        for prNum in prsDict.keys():
            deviation_from_average_time_spent_open = prsDict[prNum]["time_spent_open_days"] - averageTimeSpentOpen
            prsDict[prNum]["deviation_from_average_time_spent_open"] = deviation_from_average_time_spent_open

            deviation_from_average_commits_per_comments = prsDict[prNum]["commits_per_comment"] - averageCommitsPerComment
            prsDict[prNum]["deviation_from_average_commits_per_comments"] = deviation_from_average_commits_per_comments

            # A Negative PR Difficulty suggests it's easier than normal, a positive one suggests it's more difficult.
            prsDict[prNum]["PR_Difficulty"] = round(deviation_from_average_commits_per_comments + deviation_from_average_time_spent_open, 3)


            
    writeCSV("PR_Summary_Metrics.csv", list(prsDict.values()))         

    return

def main():
    print("Cleaning data...")   
    clean_data("PRs.csv", "Commits.csv", "Comments.csv")
    print("Finished cleaning!")



if __name__ == "__main__":
    main()