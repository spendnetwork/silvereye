import json
import os
import shutil
from datetime import datetime
from os.path import join

import pytest
import pandas as pd
from django.test import Client
from django.urls import reverse
from flattentool import unflatten

import silvereye
from silvereye.helpers import GoogleSheetHelpers, prepare_base_json_from_release_df
from silvereye.ocds_csv_mapper import CSVMapper
from silvereye.management.commands.get_cf_data import fix_contracts_finder_flat_CSV

TESTS_DIR = os.path.dirname(os.path.realpath(__file__))

SILVEREYE_DIR = silvereye.__path__[0]
METRICS_SQL_DIR = os.path.join(SILVEREYE_DIR, "metrics", "sql")
CF_DAILY_DIR = os.path.join(SILVEREYE_DIR, "data", "cf_daily_csv")
HEADERS_LIST = join(CF_DAILY_DIR, "headers_min.txt")
OCDS_SCHEMA = join(SILVEREYE_DIR, "data", "OCDS", "1.1.4-release-schema.json")
CF_DIR = join(TESTS_DIR, "fixtures", "CF_CSV")


def test_unflatten_cf_daily_csv_to_jsonlist_of_release_packages():
    csv_path_or_url = join(CF_DIR, "export-2020-08-05.csv")
    output_file = join(CF_DIR, "working_files", "release_packages.json")
    clean_output_dir = join(CF_DIR, "working_files", "cleaned")
    clean_output_file = join(clean_output_dir, "cleaned.csv")

    df = pd.read_csv(csv_path_or_url)
    fixed_df = fix_contracts_finder_flat_CSV(df)
    shutil.rmtree(clean_output_dir, ignore_errors=True)
    os.makedirs(clean_output_dir)
    fixed_df.to_csv(open(clean_output_file, "w"), index=False, header=True)
    # schema = "https://standard.open-contracting.org/schema/1__1__4/release-package-schema.json"
    schema = OCDS_SCHEMA
    unflatten(clean_output_dir, output_name=output_file, input_format="csv", root_id="ocid", root_is_list=True, schema=schema)
    js = json.load(open(output_file))
    assert js


def test_fix_contracts_finder_flat_CSV():
    csv_path_or_url = join(CF_DIR, "export-2020-08-05.csv")
    df = pd.read_csv(csv_path_or_url)
    fixed_df = fix_contracts_finder_flat_CSV(df)
    assert any(fixed_df["releases/0/awards/0/items/0/id"])


def test_rename_friendly_cols_to_ocds_uri():
    pass


def convert_cf_to_release_csv(df):
    """
    Process raw CF CSV:
        - Filter columns using headers in HEADERS_LIST file
        - fix array issue with tags
    """
    CF_HEADERS_LIST = join(CF_DIR, "headers_min.txt")
    cols_list = open(CF_HEADERS_LIST).readlines()
    cols_list = [x.strip() for x in cols_list]
    fixed_df = df[df.columns.intersection(cols_list)]
    # Remove releases/0
    map_dict = dict([(col, col.replace('releases/0/', '')) for col in cols_list])
    fixed_df = fixed_df.rename(columns=map_dict)
    fixed_df = fixed_df.rename(columns={
        # 'extensions/0': 'extensions',
        'tag/0': 'tag'
    })
    return fixed_df


def test_unflatten_cf_daily_csv_using_base_json():
    CF_DIR = join(TESTS_DIR, "fixtures", "CF_CSV")
    working_dir = join(CF_DIR, "working_files")
    csv_path_or_url = join(CF_DIR, "export-2020-08-05_single_buyer.csv")
    output_file = join(working_dir, "release_packages.json")
    clean_output_dir = join(working_dir, "cleaned")
    clean_output_file = join(clean_output_dir, "cleaned.csv")
    shutil.rmtree(working_dir, ignore_errors=True)
    os.makedirs(clean_output_dir)

    df = pd.read_csv(csv_path_or_url)
    fixed_df = convert_cf_to_release_csv(df)
    fixed_df.to_csv(open(clean_output_file, "w"), index=False, header=True)
    base_json_path = join(CF_DIR, "working_files", "base.json")
    base_json = prepare_base_json_from_release_df(fixed_df, base_json_path)
    unflatten(clean_output_dir,
              base_json=base_json_path,
              output_name=output_file,
              root_list_path="releases",
              input_format="csv",
              root_id="ocid",
              root_is_list=False,
              schema=OCDS_SCHEMA)
    js = json.load(open(output_file))
    assert js


def test_convert_cf_to_1_1_tenders():
    csv_path_or_url = join(CF_DIR, "export-2020-08-01-tenders.csv")
    flat_processor = CSVMapper(csv_path=csv_path_or_url, release_type="tender")
    fixed_df = flat_processor.convert_cf_to_1_1(flat_processor.input_df)
    fixed_df = flat_processor.augment_cols(fixed_df)

    clean_output_file = join(CF_DIR, "converted.csv")
    fixed_df.to_csv(open(clean_output_file, "w"), index=False, header=True)

    simple_df = flat_processor.output_simple_csv(fixed_df)
    simple_output_file = join(CF_DIR, "tenders.csv")
    simple_df.to_csv(open(simple_output_file, "w"), index=False, header=True)


def test_convert_cf_to_1_1_awards():
    csv_path_or_url = join(CF_DIR, "export-2020-07-01_awards.csv")
    flat_processor = CSVMapper(release_type="contract", csv_path=csv_path_or_url)
    fixed_df = flat_processor.convert_cf_to_1_1(flat_processor.input_df)
    fixed_df = flat_processor.augment_cols(fixed_df)

    clean_output_file = join(CF_DIR, "converted.csv")
    fixed_df.to_csv(open(clean_output_file, "w"), index=False, header=True)

    simple_df = flat_processor.output_simple_csv(fixed_df)
    simple_output_file = join(CF_DIR, "awards.csv")
    simple_df.to_csv(open(simple_output_file, "w"), index=False, header=True)


def test_create_templates():
    templates_output_dir = join(CF_DIR, "templates")
    shutil.rmtree(templates_output_dir, ignore_errors=True)
    create_templates = CSVMapper().create_templates(templates_output_dir)
