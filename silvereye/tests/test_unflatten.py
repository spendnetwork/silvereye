import json
import os
import shutil
from os.path import join

import pytest
import pandas as pd
from flattentool import unflatten

import silvereye
from silvereye.ocds_csv_mapper import CSVMapper
from silvereye.management.commands.get_cf_data import fix_contracts_finder_flat_csv

SILVEREYE_DIR = silvereye.__path__[0]
TESTS_DIR = os.path.dirname(os.path.realpath(__file__))
CF_DAILY_DIR = os.path.join(SILVEREYE_DIR, "data", "cf_daily_csv")
OCDS_SCHEMA = join(SILVEREYE_DIR, "data", "OCDS", "1.1.4-release-schema.json")
CF_DIR = join(TESTS_DIR, "fixtures", "CF_CSV")
CF_MAPPINGS_FILE = os.path.join(SILVEREYE_DIR, "data", "csv_mappings", "contracts_finder_mappings.csv")


def test_unflatten_cf_daily_csv_to_jsonlist_of_release_packages(contracts_finder_daily_csv_df):
    output_file = join(CF_DIR, "working_files", "release_packages.json")
    clean_output_dir = join(CF_DIR, "working_files", "cleaned")
    clean_output_file = join(clean_output_dir, "cleaned.csv")

    fixed_df = fix_contracts_finder_flat_csv(contracts_finder_daily_csv_df)
    shutil.rmtree(clean_output_dir, ignore_errors=True)
    os.makedirs(clean_output_dir)
    fixed_df.to_csv(open(clean_output_file, "w"), index=False, header=True)
    # schema = "https://standard.open-contracting.org/schema/1__1__4/release-package-schema.json"
    schema = OCDS_SCHEMA
    unflatten(clean_output_dir, output_name=output_file, input_format="csv", root_id="ocid", root_is_list=True,
              schema=schema)
    js = json.load(open(output_file))
    assert js


def test_fix_contracts_finder_flat_CSV(contracts_finder_daily_csv_df):
    fixed_df = fix_contracts_finder_flat_csv(contracts_finder_daily_csv_df)
    assert any(fixed_df["releases/0/awards/0/items/0/id"])


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

    cf_mapper = CSVMapper(mappings_file=CF_MAPPINGS_FILE)
    fixed_df = fix_contracts_finder_flat_csv(df)
    fixed_df = cf_mapper.convert_cf_to_1_1(fixed_df)

    fixed_df.to_csv(open(clean_output_file, "w"), index=False, header=True)
    base_json_path = join(CF_DIR, "working_files", "base.json")
    base_json = cf_mapper.prepare_base_json_from_release_df(fixed_df, base_json_path)
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
