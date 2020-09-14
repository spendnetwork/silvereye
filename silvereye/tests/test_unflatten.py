import json
import os
import shutil
from os.path import join

import pytest
import pandas as pd
from flattentool import unflatten
from six import StringIO

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


def test_convert_cf_to_1_1_tenders():
    csv_path_or_url = join(CF_DIR, "export-2020-08-01-tenders.csv")
    simple_csv_mapper = CSVMapper(csv_path=csv_path_or_url, release_type="tender")
    cf_mapper = CSVMapper(
        mappings_file=os.path.join(SILVEREYE_DIR, "data", "csv_mappings", "contracts_finder_mappings.csv"))
    fixed_df = cf_mapper.convert_cf_to_1_1(simple_csv_mapper.input_df)

    clean_output_file = join(CF_DIR, "converted.csv")
    fixed_df.to_csv(open(clean_output_file, "w"), index=False, header=True)

    simple_df = simple_csv_mapper.output_simple_csv(fixed_df)
    simple_output_file = join(CF_DIR, "tenders.csv")
    simple_df.to_csv(open(simple_output_file, "w"), index=False, header=True)


def test_convert_cf_to_1_1_awards():
    csv_path_or_url = join(CF_DIR, "export-2020-07-01_awards.csv")
    simple_csv_mapper = CSVMapper(release_type="award", csv_path=csv_path_or_url)
    cf_mapper = CSVMapper(
        mappings_file=os.path.join(SILVEREYE_DIR, "data", "csv_mappings", "contracts_finder_mappings.csv"))
    fixed_df = cf_mapper.convert_cf_to_1_1(simple_csv_mapper.input_df)

    clean_output_file = join(CF_DIR, "converted.csv")
    fixed_df.to_csv(open(clean_output_file, "w"), index=False, header=True)

    simple_df = simple_csv_mapper.output_simple_csv(fixed_df)
    simple_output_file = join(CF_DIR, "awards.csv")
    simple_df.to_csv(open(simple_output_file, "w"), index=False, header=True)


def test_create_templates():
    templates_output_dir = join(CF_DIR, "templates")
    shutil.rmtree(templates_output_dir, ignore_errors=True)
    create_templates = CSVMapper(release_type="award").create_simple_CSV_templates(templates_output_dir)

    tender_csv_path = os.path.join(templates_output_dir, "tender_template.csv")
    assert os.path.exists(tender_csv_path)
    df = pd.read_csv(tender_csv_path, nrows=0)
    assert "Tender Title" in df.columns

    award_csv_path = os.path.join(templates_output_dir, "award_template.csv")
    assert os.path.exists(award_csv_path)
    df = pd.read_csv(award_csv_path, nrows=0)
    assert "Award Title" in df.columns

    spend_csv_path = os.path.join(templates_output_dir, "spend_template.csv")
    assert os.path.exists(spend_csv_path)
    df = pd.read_csv(spend_csv_path, nrows=0)
    assert "Transaction ID" in df.columns


def test_create_tender_template():
    io = StringIO()
    CSVMapper().create_simple_csv_template(io, release_type="tender")
    io.seek(0)
    df = pd.read_csv(io, nrows=0)
    assert "Tender Title" in df.columns


def test_create_award_template():
    io = StringIO()
    CSVMapper().create_simple_csv_template(io, release_type="award")
    io.seek(0)
    df = pd.read_csv(io, nrows=0)
    assert "Award Title" in df.columns


def test_create_spend_template():
    io = StringIO()
    CSVMapper().create_simple_csv_template(io, release_type="spend")
    io.seek(0)
    df = pd.read_csv(io, nrows=0)
    assert "Transaction ID" in df.columns


def test_convert_simple_csv_to_ocds_csv(simple_csv_submission_path, tmp_path):
    tmpfile_path = os.path.join(tmp_path, "tender.csv")
    shutil.copyfile(simple_csv_submission_path, tmpfile_path)
    mapper = CSVMapper(csv_path=tmpfile_path)
    ocds_df = mapper.convert_simple_csv_to_ocds_csv(tmpfile_path)

    assert "initiationType" in ocds_df.columns


def test_convert_simple_award_csv_to_ocds_csv(simple_award_csv_submission_path, tmp_path):
    tmpfile_path = os.path.join(tmp_path, "award.csv")
    shutil.copyfile(simple_award_csv_submission_path, tmpfile_path)
    mapper = CSVMapper(csv_path=tmpfile_path)
    ocds_df = mapper.convert_simple_csv_to_ocds_csv(tmpfile_path)

    assert "initiationType" in ocds_df.columns


def test_rename_friendly_cols_to_ocds_uri(simple_csv_submission_path, simple_csv_submission_df):
    renamed_df = CSVMapper(simple_csv_submission_path).rename_friendly_cols_to_ocds_uri(simple_csv_submission_df)
    assert "tender/title" in renamed_df.columns


def test_default_referenced_mapping(simple_csv_submission_path):
    mapper = CSVMapper(simple_csv_submission_path)
    new_df = mapper.rename_friendly_cols_to_ocds_uri(mapper.input_df)
    mapper.detect_notice_type(new_df)
    new_df = mapper.augment_cols(new_df)

    assert new_df.loc[0, "parties/0/id"] == "buyer_id_0"
    assert new_df.loc[1, "parties/0/id"] == "buyer"

    assert "awards/0/suppliers/0/id" not in new_df.columns


def test_default_referenced_award_mapping(simple_award_csv_submission_path):
    mapper = CSVMapper(simple_award_csv_submission_path)
    new_df = mapper.rename_friendly_cols_to_ocds_uri(mapper.input_df)
    mapper.detect_notice_type(new_df)
    new_df = mapper.augment_cols(new_df)

    assert new_df.loc[0, "parties/0/id"] == "buyer"
    assert new_df.loc[1, "parties/0/id"] == "buyer"

    assert "awards/0/suppliers/0/id" in new_df.columns


@pytest.mark.parametrize(
    ("cf_header", "expected_mapping"),
    [
        ("releases/0/tender/milestones/0/dueDate", "tender/contractPeriod/startDate"),
        ("releases/0/buyer/name", "parties/0/name"),
        ("releases/0/awards/0/suppliers/0/name", "parties/1/name")
    ]
)
def test_contracts_finder_mappings(cf_header, expected_mapping):
    cf_mapper = CSVMapper(
        mappings_file=os.path.join(SILVEREYE_DIR, "data", "csv_mappings", "contracts_finder_mappings.csv"))
    df = cf_mapper.mappings_df
    uri = df[df["contracts_finder_daily_csv_path"] == cf_header].iloc[0].get("uri")
    assert uri == expected_mapping
