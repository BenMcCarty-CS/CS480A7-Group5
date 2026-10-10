The first step to running the pipeline is running main inside of mine_prs.py - this will give you your base set of raw data. Beware it will take a long time,
it will also be able to restart its run at where it left off in the event of a crash, thanks to the fact it writes as it goes.

The next step is to run clean_data.py's main whilst supplying 3 arguments - the path to PRs csv, the path to the Commits csv, and the path to the comments csv. 
And, there you go! You've obtained your PR_Summary_Metrics, the metrics we'll be using for the study.

Our important checkpoints are a bit more special because they aren't marked by new unique files, but rather, mostly updates to our clean_data.py to add more metrics.

The artifacts we retrieved WERE through the observation period filter, so we start with a total of 60,506 pull requests in our time window. Then, we applied a 
variety of exclusions that slowly widdled down the total. First, we excluded any PR that was a draft, resulting in 57,950 PRs. We then removed any PRs that had
no changes, resulting in 57,785 PRs. We then removed any PRs that had no comments, resulting in 57,436 PRs, we then removed any PR open for 30 seconds or less,
bringing us our final total of 57,377 PRs in our data set. 