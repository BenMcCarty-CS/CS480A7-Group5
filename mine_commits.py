import os
from dotenv import load_dotenv
from datetime import datetime as dt
from zoneinfo import ZoneInfo
import requests
import csv
import json

load_dotenv()

OWNER = "zephyrproject-rtos"
REPO = "zepyhr"

CURENT_TIME = dt.now(tz=ZoneInfo("UTC")).isoformat()

START_TIME = "2021-09-01T00:00:00Z"
END_TIME = "2026-08-31T23:59:59Z"

# needs to have the {pull_number}/commits added to the end when making the call
URL = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/"

HEADERS = {
    "Accept": "appliction/vnd.github+json",
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
}

# might need a separate class for PRs that have more than 250 commits in them
PARAMS = {
    "per_page": 100,
}

# will get the commits for one PR
def make_call(url: str, prNum):
    commits = []
    page = 1
    
    while True:
        params = {**PARAMS, "page": page}
        
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        batch = response.json()
        
        print(f"Got {len(batch)} commits")

        if batch == []:
            break
        # add the prNumber a commit is in
        for b in batch:
            b["prNumber"] = prNum
        commits.extend(batch)
        page += 1
        if (len(batch) < PARAMS("per_page")):
            print(f"Fetched page: {page - 1}. Page had less than {PARAMS['per_page']} no more pages to fetch")
            break
        print(f"Fetched page: {page - 1}\nNow getting page: {page}")
    return commits
            
def get_commits() -> []:
    all_commits = []
    with open('MinedPRData.csv', 'r', newline='', encoding='utf-8') as reader:
        pr_data = csv.DictReader(reader)
        for row in pr_data:
            # the API docs say it will only return 250 commits but also says only 100 and default is 30 so idk
            if row["commits"] > 250:
                # TODO: make the logic here
                pass
            else:
                url = f"{URL}/{row["prNumber"]}/commits"
                all_commits.append(make_call(url), row["prNumber"])
    return all_commits

# TODO: Write commits to csv