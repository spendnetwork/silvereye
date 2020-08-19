import json

from datetime import datetime

import os

import numpy as np
import pandas as pd
from django.conf import settings


class CSVMapper():
    mappings_df = pd.read_csv(settings.CSV_MAPPINGS_PATH, keep_default_na=False)
    notice_types = [
        "tender",
        "award",
        "spend",
    ]

    def __init__(self, csv_path=None, release_type=None):
        self.csv_path = csv_path
        self.release_type = release_type
        self.ocid_prefix = "ocds-testprefix-"
        if csv_path:
            self.input_df = pd.read_csv(csv_path)
            self.input_df = self.input_df.replace({np.nan: None})
            self.detect_notice_type(self.input_df)
        else:
           self.input_df = None
        self.output_df = pd.DataFrame(columns=self.mappings_df["uri"])
        self.simple_mappings_df = self.mappings_df.loc[self.mappings_df[f'{self.release_type}_csv'] == "TRUE"]


    def rename_friendly_cols_to_ocds_uri(self, df):
        mapping_dict = {}
        for i, row in self.simple_mappings_df.iterrows():
            if row["csv_header"]:
                mapping_dict[row["csv_header"]] = row["uri"]
        self.output_df = df.rename(columns=mapping_dict)
        return self.output_df

    def convert_cf_to_1_1(self, df):

        # Clear cols not in mappings
        cols_list = self.simple_mappings_df["contracts_finder_daily_csv_path"].to_list()
        new_df = df[df.columns.intersection(cols_list)]
        mapping_dict = {}
        for i, row in self.mappings_df.iterrows():
            mapping_dict[row["contracts_finder_daily_csv_path"]] = row["uri"]
        new_df = new_df.rename(columns=mapping_dict)

        # Remove ocds prefix from ids for realistic data
        new_df['id'] = new_df['id'].str.replace('ocds-b5fd17-', '')
        self.output_df = new_df
        return new_df

    def augment_cols(self, df):
        for i, row in self.mappings_df.iterrows():
            # Set defaults from mapping sheet
            if row["default"]:
                df[row["uri"]] = row["default"]
            # Set references
            if row["reference"] and row["reference"] in df:
                df.loc[:, row["uri"]] = df[row["reference"]]
        df["ocid"] = self.ocid_prefix + df['id']
        df["tag"] = self.release_type
        return df

    def output_simple_csv(self, df):
        mapping_dict = {}
        for i, row in self.simple_mappings_df.iterrows():
            mapping_dict[row["uri"]] = row["csv_header"]
        new_df = df.rename(columns=mapping_dict)

        # Clear cols not in simple CSV
        cols_list = [i for i in self.simple_mappings_df["csv_header"].to_list() if i]
        new_df = new_df[new_df.columns.intersection(cols_list)]

        self.output_df = new_df
        return new_df

    def convert_simple_csv_to_ocds_csv(self, csv_path):
        df = pd.read_csv(csv_path)
        new_df = self.rename_friendly_cols_to_ocds_uri(df)
        self.detect_notice_type(new_df)
        new_df = self.augment_cols(new_df)
        new_df.to_csv(open(csv_path, "w"), index=False, header=True)
        self.output_df = new_df
        return new_df

    def create_templates(self, output_dir):
        os.makedirs(output_dir)
        tender_mappings_df = self.mappings_df.loc[self.mappings_df['tender_csv'] == "TRUE"]
        tender_df = pd.DataFrame(columns=tender_mappings_df["uri"])
        tender_df.to_csv(os.path.join(output_dir, "tender_template.csv"), index=False, header=True)

        award_mappings_df = self.mappings_df.loc[self.mappings_df['award_csv'] == "TRUE"]
        award_df = pd.DataFrame(columns=award_mappings_df["uri"])
        award_df.to_csv(os.path.join(output_dir, "award_template.csv"), index=False, header=True)

    def detect_notice_type(self, df):
        if "awards/0/id" in df.columns or "Award Title" in df.columns:
            self.release_type = "award"
        else:
            self.release_type = "tender"

    def prepare_base_json_from_release_df(self, fixed_df, base_json_path=None):
        max_release_date = datetime.strptime(max(fixed_df["date"]), '%Y-%m-%dT%H:%M:%SZ')
        base_json = {
            "version": "1.1",
            "publisher": {
                "name": fixed_df.iloc[0]["buyer/name"],
                "scheme": fixed_df.iloc[0]["buyer/identifier/scheme"],
                "uid": fixed_df.iloc[0]["buyer/identifier/id"],
            },
            "publishedDate": max_release_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "uri": "https://ocds-silvereye.herokuapp.com/"
        }
        if base_json_path:
            with open(base_json_path, "w") as writer:
                json.dump(base_json, writer, indent=2)
        return base_json
