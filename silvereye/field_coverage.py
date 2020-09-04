import pandas as pd
import os

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
sample_submisisons = os.path.join(data_dir, 'cf_daily_csv/sample_submissions')


def check_coverage(input_df, mappings_df, notice_type="tender"):

    if notice_type == "tender":
        mappings_df = mappings_df.loc[mappings_df["tender_csv"] == True]
        expected_fields = len(mappings_df)
    elif notice_type == "award":
        mappings_df = mappings_df.loc[mappings_df["award_csv"] == True]
        expected_fields = len(mappings_df)
    else:
        mappings_df = mappings_df.loc[mappings_df["spend_csv"] == True]
        expected_fields = len(mappings_df)

    coverage_output = []
    required_missing = []
    completed_fields_counts = []
    required_fields = mappings_df.loc[mappings_df['required'] == True, 'csv_header'].values.tolist()
    for i, row in input_df.iterrows():
        completed_fields_counts.append(row.count())

        critical_nulls = row.isnull()[required_fields]
        required_missing = critical_nulls[critical_nulls].index.tolist()
        if required_missing:
            coverage_output.append({'Notice ID': row['Notice ID'], 'Critical Missing Fields': required_missing})

    completion = input_df.count().div(len(input_df)).mul(100)
    missingcounts = input_df.isna().sum()
    missing_counts_nonzero = missingcounts[missingcounts != 0].sort_values(ascending=False)
    critical_report = pd.DataFrame(coverage_output)

    report = {
        "expected_fields": expected_fields,
        "required_fields": required_fields,
        "required_fields_missing": required_missing,
        "field_completion_percentage": completion,
        "counts_missing_fields": missing_counts_nonzero,
        "critical_fields_missing_by_id": critical_report,
        "completed_fields_counts": completed_fields_counts
    }
    return report
