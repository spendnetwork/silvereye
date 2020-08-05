"""
Command to create an generate publisher metrics
"""
import json
import logging
import os
import shutil
from os.path import join

import pandas as pd
import requests
from cove.input.models import SuppliedData
from django.core.files.base import ContentFile
from django.core.management import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connections
from flattentool import unflatten

import silvereye
from bluetail.helpers import UpsertDataHelpers

logger = logging.getLogger('django')

SILVEREYE_DIR = silvereye.__path__[0]
METRICS_SQL_DIR = os.path.join(SILVEREYE_DIR, "metrics", "sql")
CF_DAILY_DIR = os.path.join(SILVEREYE_DIR, "data", "cf_daily_csv")
HEADERS_LIST = join(CF_DAILY_DIR, "headers_min.txt")

def import_cf_csv(csv):
    pass

def fix_df(df):
    # Filter columns and fix array issue
    cols_list = open(HEADERS_LIST).readlines()
    cols_list = [x.strip() for x in cols_list]
    fixed_df = df[df.columns.intersection(cols_list)]
    fixed_df = fixed_df.rename(columns={
        'extensions/0': 'extensions',
        'releases/0/tag/0': 'releases/0/tag'
    })
    return fixed_df


def fix_json_package(package):
    # Set publisher name to buyer name
    buyer_name = package["releases"][0]["buyer"]["name"]
    package["publisher"]["name"] = buyer_name
    return package


class Command(BaseCommand):
    help = "Generates publisher metrics for tenders"

    def handle(self, *args, **kwargs):

        daily_csv_path = join(CF_DAILY_DIR, "export-2020-08-05.csv")
        dir = os.path.dirname(daily_csv_path)
        output_file = join(dir, "release_packages.json")
        clean_output_dir = join(dir, "cleaned")
        clean_output_file = join(clean_output_dir, "cleaned.csv")
        df = pd.read_csv(daily_csv_path)
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
                # created=published_date,
                # current_app="silvereye",
            )

            # supplied_data = SuppliedData(id=cf_id)
            # supplied_data.current_app = "silvereye"
            supplied_data.original_file.save("release_package.json", ContentFile(json.dumps(package, indent=2)))
            supplied_data.save()

            json_string = json.dumps(
                package,
                indent=2,
                sort_keys=True,
                cls=DjangoJSONEncoder
            )
            UpsertDataHelpers().upsert_ocds_data(json_string, supplied_data)

        pass
