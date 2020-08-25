
import pandas as pd
import numpy as np
import os

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
sample_submisisons = os.path.join(data_dir, 'cf_daily_csv/sample_submissions')


def check_coverage(input_df, mappings_df, notice_type="tender"):

    if notice_type == "tender":
        mappings_df = mappings_df.loc[mappings_df["tender_csv"] == 'TRUE']
        expected_fields = len(mappings_df)
    elif notice_type == "award":
        mappings_df = mappings_df.loc[mappings_df["award_csv"] == 'TRUE']
        expected_fields = len(mappings_df)
    else:
        mappings_df = mappings_df.loc[mappings_df["spend_csv"] == 'TRUE']
        expected_fields = len(mappings_df)

    coverage_output = []
    completed_fields_counts = []
    critical_fields = mappings_df.loc[mappings_df['nullable'] == False, 'csv_header'].values.tolist()
    for i, row in input_df.iterrows():

        completed_fields_counts.append(row.count())

        critical_nulls = row.isnull()[critical_fields]
        critical_missing = critical_nulls[critical_nulls].index.tolist()
        if critical_missing:
            coverage_output.append({'Notice ID': row['Notice ID'], 'Critical Missing Fields': critical_missing})

    completion = input_df.count().div(len(input_df)).mul(100)
    missingcounts = input_df.isna().sum()
    missing_counts = missingcounts[missingcounts != 0].sort_values(ascending=False)
    critical_report = pd.DataFrame(coverage_output)

    report = {
        "expected_fields": expected_fields,
        "completion": completion,
        "counts_missing_fields": missing_counts,
        "critical_fields_missing_by_id": critical_report,
        "completed_fields_counts": completed_fields_counts
    }
    return report


def create_context(expected_fields, completed_fields_counts):

    av_completion = np.mean(completed_fields_counts)
    min_completion = min(completed_fields_counts)
    max_completion = max(completed_fields_counts)

    context = {
        "total expected fields": expected_fields,
        "average field completion": av_completion,
        "minimum field completion": min_completion,
        "maximum field completion": max_completion,
    }

    return context

