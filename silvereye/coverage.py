
import pandas as pd
import numpy as np
import os

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/csv_mappings')
data_path = os.path.join(data_dir, 'awards.csv')
mappings_path = os.path.join(data_dir, 'coverage_mappings.csv')


def check_coverage(input_df, mappings_df, notice_type="tender"):

    if notice_type == "tender":
        mappings_df = mappings_df.loc[mappings_df["tender_csv"] == 1]
        expected_fields = len(mappings_df)
    elif notice_type == "contract":
        mappings_df = mappings_df.loc[mappings_df["contract_csv"] == 1]
        expected_fields = len(mappings_df)
    #TODO should spend be added here?

    coverage_output = []
    completed_fields_counts = []
    missing_count_df = pd.DataFrame(columns=input_df.columns)
    critical_fields = mappings_df.loc[mappings_df['nullable'] == False, 'csv_header'].values.tolist()
    for i, row in input_df.iterrows():

        if not row['Notice ID']:
            row['Notice ID'] = 'ID missing'
        completed_fields_counts.append(row.count())

        nulls = row.isnull()

        # could include all missing fields too?
        # missing = nulls[nulls].index.tolist()

        critical_nulls = nulls[critical_fields]
        critical_missing = critical_nulls[critical_nulls].index.tolist()
        if not critical_missing:
            critical_missing = None

        coverage_output.append({'Notice ID': row['Notice ID'], 'Critical Missing Fields': critical_missing})
        missing_count_df.append(nulls.to_dict(), ignore_index=True)

    missingcounts = input_df.isna().sum()
    missingcounts = missingcounts[missingcounts != 0].sort_values(ascending=False)

    coverage_output_df = pd.DataFrame(coverage_output)
    critical_report = coverage_output_df.dropna()

    av_completion = np.mean(completed_fields_counts)
    min_completion = min(completed_fields_counts)
    max_completion = max(completed_fields_counts)

    # TODO how should the value be given here?
    context = {
        "counts of missing fields": missingcounts,
        "critical fields missing by id": critical_report,
        "total expected fields": expected_fields,
        "average field completion": av_completion,
        "minimum field completion": min_completion,
        "maximum field completion": max_completion,
    }
    return context


def main():

    df_in = pd.read_csv(data_path)
    df_mapping = pd.read_csv(mappings_path)

    context = check_coverage(df_in, df_mapping, notice_type='contract')

    assert context


if __name__ == '__main__':
    main()
