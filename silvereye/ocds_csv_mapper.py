import json
from collections import OrderedDict

from datetime import datetime

import os

import dateparser
import numpy as np
import pandas as pd
from django.conf import settings

from silvereye.field_coverage import check_coverage


class CSVMapper:
    """
    Class to handle mapping of CSV headers between simple CSV and flattened OCDS
    """
    mappings_file = settings.CSV_MAPPINGS_PATH

    notice_types = [
        "tender",
        "award",
        "spend",
    ]

    def __init__(self, csv_path=None, release_type=None, mappings_file=None):
        if mappings_file:
            self.mappings_file = mappings_file
        self.mappings_df = self._read_csv_to_dataframe(self.mappings_file)
        self.csv_path = csv_path
        self.release_type = release_type
        self.ocid_prefix = "ocds-testprefix-"
        if csv_path:
            self.input_df = self._read_csv_to_dataframe(csv_path)
            if not release_type:
                self.detect_notice_type(self.input_df)
        else:
            self.input_df = None
        if self.release_type:
            self.simple_mappings_df = self.mappings_df.loc[self.mappings_df[f'{self.release_type}_csv'] == True]
            self.simple_csv_df = self.mappings_df.loc[
                (self.mappings_df[f'{self.release_type}_csv'] == True) & (pd.notnull(self.mappings_df['csv_header']))]

    def _read_csv_to_dataframe(self, mappings_csv_path):
        df = pd.read_csv(mappings_csv_path, na_values=[""])
        df = df.replace({np.nan: None})
        return df

    # def _map_and_crop_df(self, df, mappings_df, map_from_col="orig", map_to_col="target"):
    #     """
    #     utility func to rename cols and remove any not in the mappings_df
    #     """
    #     # Clear cols not in mappings
    #     cols_list = self.simple_mappings_df["contracts_finder_daily_csv_path"].to_list()
    #     new_df = df[df.columns.intersection(cols_list)]
    #     mapping_dict = {}
    #     for i, row in self.mappings_df.iterrows():
    #         if row[map_from_col]:
    #             mapping_dict[row[map_from_col]] = row[map_to_col]
    #     new_df = new_df.rename(columns=mapping_dict)

    def rename_friendly_cols_to_ocds_uri(self, df):
        """
        Use the class.mappings_df to rename simple CSV headers to OCDS URI paths for unflattening

        :param df: pandas dataframe of a simple CSV file
        :return:
        """
        mapping_dict = {}
        # Remove unknown columns
        cols_list = self.simple_mappings_df["csv_header"].to_list()
        new_df = df[df.columns.intersection(cols_list)]

        # rename simple CSV headers to OCDS uri headers
        for i, row in self.simple_mappings_df.iterrows():
            if row["csv_header"]:
                mapping_dict[row["csv_header"]] = row["uri"]
        new_df = new_df.rename(columns=mapping_dict)
        return new_df

    def convert_cf_to_1_1(self, contracts_finder_df):
        """
        Convenience function to prepare CF data as sample data for submission

        Use provided mappings_df to :
            - remove columns not wanted for Silvereye
            - map the CF headers to OCDS release headers
            - remove OCID prefixes from release ids

        :param contracts_finder_df: dataframe of Contracts Finder Daily CSV data
        :return:
        """
        # Clear cols not in mappings
        cf_mappings = self.mappings_df.loc[pd.notnull(self.mappings_df['uri'])]
        cols_list = cf_mappings["contracts_finder_daily_csv_path"].to_list()
        new_df = contracts_finder_df[contracts_finder_df.columns.intersection(cols_list)]

        mapping_dict = {}
        for i, row in cf_mappings.iterrows():
            mapping_dict[row["contracts_finder_daily_csv_path"]] = row["uri"]
        new_df = new_df.rename(columns=mapping_dict)

        # Add buyer refs
        new_df['buyer/name'] = new_df['parties/0/name']

        # Remove ocds prefix from ids for realistic data
        new_df['id'] = new_df['id'].str.replace('ocds-b5fd17-', '')
        return new_df

    def augment_cols(self, df):
        """
        Use the mappings_df to augment a given dataframe with default/referred fields
        Needed to populate additional fields for unflattening.

        :param df: dataframe of a simple CSV with headers mapped to OCDS
        :return:
        """
        for i, row in self.simple_mappings_df.iterrows():
            ocds_header = row["uri"]
            default_value = row["default"]
            reference_header = row["reference"]
            # Set defaults from mapping sheet
            if default_value:
                df[ocds_header] = default_value
            # Set references
            if reference_header and reference_header in df.columns:
                if not ocds_header in df.columns:
                    df.loc[:, ocds_header] = df[reference_header]
                else:
                    df.loc[:, ocds_header] = df.apply(
                        lambda row: row[reference_header] if pd.notnull(row[reference_header]) else row[ocds_header],
                        axis=1)

        df['ocid'] = df.apply(lambda row: f"{self.ocid_prefix}{str(row['id'])}", axis=1)

        if self.release_type == "spend":
            df["tag"] = "implementation"
        else:
            df["tag"] = self.release_type

        return df

    def output_simple_csv(self, df):
        mapping_dict = OrderedDict()
        for i, row in self.simple_mappings_df.iterrows():
            mapping_dict[row["uri"]] = row["csv_header"]
        new_df = df.rename(columns=mapping_dict)

        # Clear cols not in simple CSV
        cols_list = [i for i in self.simple_csv_df["csv_header"].to_list() if i]
        new_df = new_df[new_df.columns.intersection(cols_list)]

        # Augment expected simple CSV cols
        new_df = new_df.reindex(columns=cols_list)

        return new_df

    def parse_dates(self, df):
        def get_datetime(datestring):
            d = dateparser.parse(str(datestring), settings={"STRICT_PARSING": True})
            if isinstance(d, datetime):
                return d.strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                return datestring

        for col in df.columns:
            if "date" in col.lower():
                df[col] = df.apply(lambda row: get_datetime(row[col]), axis=1)
        return df

    def convert_simple_csv_to_ocds_csv(self, csv_path):
        df = pd.read_csv(csv_path)
        new_df = self.rename_friendly_cols_to_ocds_uri(df)
        if not self.release_type:
            self.detect_notice_type(new_df)
        new_df = self.parse_dates(new_df)
        new_df = self.augment_cols(new_df)
        new_df.to_csv(open(csv_path, "w"), index=False, header=True)
        return new_df

    def create_simple_CSV_templates(self, output_dir):
        """
        Create all simple CSV templates in given directory

        :param output_dir: Directory path
        :return:
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        tender_csv_path = os.path.join(output_dir, "tender_template.csv")
        self.create_simple_csv_template(tender_csv_path, "tender")

        award_csv_path = os.path.join(output_dir, "award_template.csv")
        self.create_simple_csv_template(award_csv_path, "award")

        spend_csv_path = os.path.join(output_dir, "spend_template.csv")
        self.create_simple_csv_template(spend_csv_path, "spend")

    def create_simple_csv_template(self, output_path, release_type):
        """
        Create a simple CSV output from the mappings file

        :param output_path: File path of buffer
        :param release_type: notice type
        :return:
        """
        self.simple_csv_df = self.mappings_df.loc[
            (self.mappings_df[f'{release_type}_csv'] == True) & (pd.notnull(self.mappings_df['csv_header']))]
        df = pd.DataFrame(columns=self.simple_csv_df["csv_header"])
        df.to_csv(output_path, index=False, header=True)

    def detect_notice_type(self, df):
        """
        Attempt to detect the type of notice from a dataframe of either:
            - simple CSV
            - flat OCDS release

        :param df: pandas dataframe
        :return:
        """
        if "awards/0/title" in df.columns or "Award Title" in df.columns:
            self.release_type = "award"
        elif "contracts/0/implementation/transactions/0/id" in df.columns or "Transaction ID" in df.columns:
            self.release_type = "spend"
        elif "tender/title" in df.columns or "Tender Title" in df.columns:
            self.release_type = "tender"
        else:
            raise ValueError("Unknown notice type")

    def prepare_base_json_from_release_df(self, release_df, base_json_path=None):
        """
        Function to create a "base_json" file for use in unflattening OCDS releases.
        Uses first release in the DF to set the publisher metadata in the base_json.
        For a consistent release package, first filter the release_df to only contain a single buyer.
        Used to prepare Contracts Finder sample release packages in Silvereye.

        :param release_df: pandas dataframe of releases
        :param base_json_path: output path to store the JSON file
        :return:
        """
        max_release_date = datetime.strptime(max(release_df["date"]), '%Y-%m-%dT%H:%M:%SZ')
        base_json = {
            "version": "1.1",
            "publisher": {
                "name": release_df.iloc[0]["buyer/name"],
                "scheme": release_df.iloc[0]["parties/0/identifier/scheme"],
                "uid": release_df.iloc[0]["parties/0/identifier/id"],
            },
            "publishedDate": max_release_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "uri": "https://ocds-silvereye.herokuapp.com/"
        }
        if base_json_path:
            with open(base_json_path, "w") as writer:
                json.dump(base_json, writer, indent=2)
        return base_json

    def run_coverage(self):
        """ Returns a dictionary containing:

            "expected_fields": (int) The number of possible fields given in the input csv.
            "completion": (Series) The percentage of completion of each field given in the input csv.
            "counts_missing_fields": (Series) The occurrence of null values by header.
            "critical_fields_missing_by_id": (DataFrame) Details of the ID and headers where values are missing.
            "completed_fields_counts": (list) The number of completed fields per row.

        """
        coverage_results = check_coverage(self.input_df, self.simple_csv_df, notice_type=self.release_type)

        # TODO add these to db or separate report?
        # self.completion = coverage_results["completion"]
        # self.missing_field_counts = coverage_results["counts_missing_fields"]
        # self.critical_missing_by_id = coverage_results["critical_fields_missing_by_id"]

        return coverage_results

    def get_coverage_context(self):

        coverage_results = self.run_coverage()
        expected_fields = coverage_results["expected_fields"]
        completed_fields_counts = coverage_results["completed_fields_counts"]

        av_completion = np.mean(completed_fields_counts)
        min_completion = min(completed_fields_counts)
        max_completion = max(completed_fields_counts)

        context = {
            "required_fields_missing": coverage_results.get("required_fields_missing"),
            "total_expected_fields": expected_fields,
            "average_field_completion": av_completion,
            "minimum_field_completion": min_completion,
            "maximum_field_completion": max_completion,
        }

        return context
