import json
from datetime import datetime, timezone
import logging
import os
import re
from urllib.parse import urlparse, parse_qsl, urlencode

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import get_storage_class
import requests
import pandas as pd
import numpy as np

from bluetail.helpers import UpsertDataHelpers
from silvereye.models import FileSubmission

logger = logging.getLogger(__name__)


class S3_helpers():
    def retrieve_data_from_S3(self, id):
        logger.info("Attempting to download file for SuppliedData from S3: %s", id)

        upsert_helper = UpsertDataHelpers()
        s3_storage = get_storage_class(settings.S3_FILE_STORAGE)()

        directories, filenames = s3_storage.listdir(name=id)

        for filename in filenames:
            original_file_path = os.path.join(id, filename)
            logger.info(f"Downloading {original_file_path}")
            filename_root = os.path.splitext(filename)[0]

            # Create FileSubmission entry
            supplied_data, created = FileSubmission.objects.update_or_create(
                id=id,
                defaults={
                    "current_app": "silvereye",
                    "original_file": original_file_path,
                }
            )

            # Extract created date from filename if possible
            try:
                filename_datetime = datetime.strptime(filename_root, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                supplied_data.created = filename_datetime
            except ValueError:
                logger.debug("Couldn't extract datetime from filename")

            supplied_data.save()
            sync_with_s3(supplied_data)

            # package_json_raw = s3_storage._open(original_file_path)
            # package_json_dict = json.load(package_json_raw)
            # package_json = json.dumps(package_json_dict)
            #
            # upsert_helper.upsert_ocds_data(package_json, supplied_data=supplied_data)


def sync_with_s3(supplied_data):
    logger.info("Syncing supplied_data original_file with S3")
    s3_storage = get_storage_class(settings.S3_FILE_STORAGE)()
    original_filename = supplied_data.original_file.name.split(os.path.sep)[1]
    original_file_path = supplied_data.original_file.path
    # Sync to S3
    if os.path.exists(original_file_path):
        if not s3_storage.exists(supplied_data.original_file.name):
            logger.info("Storing to S3: %s", supplied_data.original_file.name)
            local_file = supplied_data.original_file.read()
            # Temporarily change the storage for the original_file FileField to save to S3
            supplied_data.original_file.storage = s3_storage
            supplied_data.original_file.save(original_filename, ContentFile(local_file))
            # Put storage back to DEFAULT_FILE_STORAGE for
            supplied_data.original_file.storage = get_storage_class(settings.DEFAULT_FILE_STORAGE)()
    # Sync from S3 if not local
    if not os.path.exists(original_file_path):
        if s3_storage.exists(supplied_data.original_file.name):
            logger.info("Retrieving from S3: %s", supplied_data.original_file.name)
            # Switch to S# storage and read file
            supplied_data.original_file.storage = s3_storage
            s3_file = supplied_data.original_file.read()

            supplied_data.original_file.storage = get_storage_class(settings.DEFAULT_FILE_STORAGE)()
            supplied_data.original_file.save(original_filename, ContentFile(s3_file))


class GoogleSheetHelpers():
    def get_sheet(self, url=""):
        # response = requests.get('https://docs.google.com/spreadsheet/ccc?key=0ArM5yzzCw9IZdEdLWlpHT1FCcUpYQ2RjWmZYWmNwbXc&output=csv')
        # XLSX download
        # response = requests.get('https://doc-0s-9k-docs.googleusercontent.com/docs/securesc/n0brkuvlm1o8v4u5up5nq9pasjli738t/e8277pb9tjvu5qsf4c9plmqjshmaadtj/1595943150000/07589777472805171581/07589777472805171581/1FWayBu0AogNhpCNdBUY8JYHHIHYIsTV2?e=download&h=03732756254954671626&authuser=0&nonce=k5isku8rmg6qc&user=07589777472805171581&hash=6qunlod35ocgdevm17se8e9s8k6s7pl2')
        # drive shared link
        # https://drive.google.com/file/d/1FWayBu0AogNhpCNdBUY8JYHHIHYIsTV2/view?usp=sharing
        response = requests.get('https://docs.google.com/spreadsheets/d/1Wkad_nigbS6xti8X0bzagfi8Hy5R2JvggtOMPQSvOpg/export?format=csv&gid=0')
        c = response.content
        return c

    def fix_url(self, url):
        if "docs.google.com/spreadsheets/" in url:
            # file_id = re.search(r"gid=([0-9]+)", parsed.fragment).group(1)

            if "xlsx" in url:
                url = "https://drive.google.com/uc?export=download&id=1FWayBu0AogNhpCNdBUY8JYHHIHYIsTV2"
                return url
            if "export" not in url:
                parsed = urlparse(url)
                if parsed.path.endswith("edit"):
                    gid = re.search(r"gid=([0-9]+)", parsed.fragment).group(1)
                    # guid = parsed.fragment.split("gid=")
                    parsed = parsed._replace(path=parsed.path.replace("edit", "export"))
                    # parsed.path = parsed.path.replace("edit", "export")
                    query = dict(parse_qsl(parsed.query))
                    query["format"] = "csv"
                    query["gid"] = gid
                    query2 = urlencode(query)
                    parsed = parsed._replace(query=query2)
                    parsed = parsed._replace(fragment="")
                    url_new = parsed.geturl()
                    return url_new
        return url


# CF data prep
def prepare_base_json_from_release_df(fixed_df, base_json_path=None):
    max_release_date = datetime.strptime(max(fixed_df["date"]), '%Y-%m-%dT%H:%M:%SZ')
    base_json = {
        "version": "1.1",
        "publisher": {
            "name": fixed_df.iloc[0]["buyer/name"],
            "scheme": fixed_df.iloc[0]["buyer/identifier/scheme"],
            "uid": fixed_df.iloc[0]["buyer/identifier/id"],
        },
        "publishedDate": max_release_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
        # "license": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/2/",
        # "publicationPolicy": "https://www.gov.uk/government/publications/open-contracting",
        "uri": "https://ocds-silvereye.herokuapp.com/"
    }
    if base_json_path:
        with open(base_json_path, "w") as writer:
            json.dump(base_json, writer, indent=2)
    return base_json


class CSVMapper():
    mappings_df = pd.read_csv(settings.CSV_MAPPINGS_PATH, keep_default_na=False)
    notice_types = [
        "tender",
        "contract",
        "spend",
    ]

    def __init__(self, csv_path=None, release_type=None):
        self.csv_path = csv_path
        self.release_type = release_type
        self.ocid_prefix = "ocds-testprefix-"
        if csv_path:
            self.input_df = pd.read_csv(csv_path)
            self.input_df = self.input_df.replace({np.nan: None})
        else:
           self.input_df = None
        self.output_df = pd.DataFrame(columns=self.mappings_df["uri"])

    def rename_friendly_cols_to_ocds_uri(self, df):
        mapping_dict = {}
        for i, row in self.mappings_df.iterrows():
            if row["csv_header"]:
                mapping_dict[row["csv_header"]] = row["uri"]
        self.output_df = df.rename(columns=mapping_dict)
        return self.output_df

    def convert_cf_to_1_1(self, df):
        # Clear cols not in mappings
        filtered_mappings_df = self.mappings_df.loc[self.mappings_df[f'{self.release_type}_csv'] == "TRUE"]
        cols_list = filtered_mappings_df["contracts_finder_daily_csv_path"].to_list()
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
        for i, row in self.mappings_df.iterrows():
            mapping_dict[row["uri"]] = row["csv_header"]
        new_df = df.rename(columns=mapping_dict)

        # Clear cols not in simple CSV
        cols_list = [i for i in self.mappings_df["csv_header"].to_list() if i]
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

        contract_mappings_df = self.mappings_df.loc[self.mappings_df['contract_csv'] == "TRUE"]
        contract_df = pd.DataFrame(columns=contract_mappings_df["uri"])
        contract_df.to_csv(os.path.join(output_dir, "contract_template.csv"), index=False, header=True)

    def detect_notice_type(self, df):
        if "awards/0/id" in df.columns:
            self.release_type = "contract"
        elif "id" in df.columns:
            self.release_type = "tender"

