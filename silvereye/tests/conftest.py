import os
from os.path import join

import pytest
import pandas as pd

import silvereye

SILVEREYE_DIR = silvereye.__path__[0]
TESTS_DIR = os.path.dirname(os.path.realpath(__file__))
CF_DIR = join(TESTS_DIR, "fixtures", "CF_CSV")



@pytest.fixture()
def contracts_finder_daily_csv_df():
    csv_path_or_url = join(CF_DIR, "export-2020-08-05.csv")
    df = pd.read_csv(csv_path_or_url)
    return df


@pytest.fixture()
def simple_csv_submission_path():
    csv_path_or_url = join(TESTS_DIR, "fixtures", "CSV_input", "highways-england-tender_20200817-20200824.csv")
    return csv_path_or_url


@pytest.fixture()
def simple_award_csv_submission_path():
    csv_path_or_url = join(TESTS_DIR, "fixtures", "CSV_input", "telford-wrekin-council-award_20200727-20200803.csv")
    return csv_path_or_url


@pytest.fixture()
def simple_csv_submission_df(simple_csv_submission_path):
    df = pd.read_csv(simple_csv_submission_path)
    return df
