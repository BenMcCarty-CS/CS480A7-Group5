import csv

def calculate_PR_difficulty(row): #This calculates review difficulty

    return int(row['num_review_comments']) + float(row['time_spent_open_days'])

def analyse_data(cleanedDataFileName: str, outputFileName: str):

    prsDict = {}
    with open(cleanedDataFileName, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) + ['PR_Difficulty']
        with open(outputFileName, mode='w', newline='', encoding='utf-8') as out_f:
            writer = csv.DictWriter(out_f, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                row['PR_Difficulty'] = calculate_PR_difficulty(row)
                writer.writerow(row)

    pass

def main():
    print("Analysing data...")   
    analyse_data("clean_data/PR_Summary_Metrics.csv", "clean_data/analyzed_data.csv")
    print("Finished analysing!")



if __name__ == "__main__":
    main()