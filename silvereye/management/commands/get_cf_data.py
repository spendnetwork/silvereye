"""
Command to create an generate publisher metrics
"""
from datetime import datetime

import json
import logging
import os
import shutil
from os.path import join

import pandas as pd
from cove.input.models import SuppliedData
from django.core.files.base import ContentFile
from django.core.management import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from flattentool import unflatten

import silvereye
from bluetail.helpers import UpsertDataHelpers

logger = logging.getLogger('django')

SILVEREYE_DIR = silvereye.__path__[0]
METRICS_SQL_DIR = os.path.join(SILVEREYE_DIR, "metrics", "sql")
CF_DAILY_DIR = os.path.join(SILVEREYE_DIR, "data", "cf_daily_csv")
HEADERS_LIST = join(CF_DAILY_DIR, "headers_min.txt")


def fix_df(df):
    """
    Process raw CF CSV:
        - Filter columns using headers in HEADERS_LIST file
        - fix array issue with tags
    """
    cols_list = open(HEADERS_LIST).readlines()
    cols_list = [x.strip() for x in cols_list]
    fixed_df = df[df.columns.intersection(cols_list)]
    fixed_df = fixed_df.rename(columns={
        # 'extensions/0': 'extensions',
        'releases/0/tag/0': 'releases/0/tag'
    })
    return fixed_df


def fix_json_package(package):
    """Set publisher name to buyer name"""
    buyer_name = package["releases"][0]["buyer"]["name"]
    package["publisher"]["name"] = buyer_name
    return package


def process_df_csv(csv_path_or_url):
    """
    Take path or URL to a Contracts Finder API flat CSV output and insert all releases into Silvereye database
    """
    output_file = join(CF_DAILY_DIR, "release_packages.json")
    clean_output_dir = join(CF_DAILY_DIR, "cleaned")
    clean_output_file = join(clean_output_dir, "cleaned.csv")
    df = pd.read_csv(csv_path_or_url)
    fixed_df = fix_df(df)
    shutil.rmtree(clean_output_dir, ignore_errors=True)
    os.makedirs(clean_output_dir)
    fixed_df.to_csv(open(clean_output_file, "w"), index=False, header=True)
    schema = "https://standard.open-contracting.org/schema/1__1__4/release-package-schema.json"
    unflatten(clean_output_dir, output_name=output_file, input_format="csv", root_id="ocid", root_is_list=True, schema=schema)
    js = json.load(open(output_file))
    for package in js:
        package = fix_json_package(package)

        cf_id = os.path.splitext(os.path.split(package["uri"])[1])[0]
        release_id = package["releases"][0]["id"]
        published_date = package["publishedDate"]

        # Create SuppliedData entry
        supplied_data, created = SuppliedData.objects.update_or_create(
            id=cf_id,
            defaults={
                "created": published_date,
                "current_app": "silvereye",
            }
        )
        supplied_data.created = published_date
        supplied_data.original_file.save("release_package.json", ContentFile(json.dumps(package, indent=2)))
        supplied_data.save()

        json_string = json.dumps(
            package,
            indent=2,
            sort_keys=True,
            cls=DjangoJSONEncoder
        )
        UpsertDataHelpers().upsert_ocds_data(json_string, supplied_data)


class Command(BaseCommand):
    help = "Inserts Contracts Finder data using Flat CSV OCDS from the CF API.\nhttps://www.contractsfinder.service.gov.uk/apidocumentation/Notices/1/GET-Harvester-Notices-Data-CSV"

    def add_arguments(self, parser):
        parser.add_argument("--start_date", help="Import from date. YYYY-MM-DD")
        parser.add_argument("--end_date", help="Import to date. YYYY-MM-DD")
        parser.add_argument("--file_path", type=str, help="File path to CSV data to insert.")
        # parser.add_argument("--anonymise", action='store_true', help="Anonymise names/addresses during insert")

    def handle(self, *args, **kwargs):

        if kwargs.get("start_date"):
            start_date = kwargs.get("start_date")
            end_date = kwargs.get("end_date", datetime.today())
            daterange = pd.date_range(start_date, end_date)
            logger.info("Downloading Contracts Finder data from %s to %s", start_date, end_date)
            for date in daterange:
                try:
                    url = f"https://www.contractsfinder.service.gov.uk/Harvester/Notices/Data/CSV/{date.year}/{date.month:02}/{date.day:02}"
                    logger.info("Processing URL: %s", url)
                    process_df_csv(url)
                except TypeError:
                    logger.exception("Error with file: %s", url)
        elif kwargs.get("file_path"):
            process_df_csv(kwargs.get("file_path"))
        else:
            self.print_help('manage.py', '<your command name>')
