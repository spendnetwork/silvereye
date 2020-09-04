
import pandas as pd
import os

from silvereye.ocds_csv_mapper import CSVMapper

TESTS_DIR = os.path.dirname(os.path.realpath(__file__))

data_dir = os.path.join(TESTS_DIR, 'fixtures/OCDS_coverage')


def test_check_tenders_coverage():

    csv_tender_path = os.path.join(data_dir, 'tenders.csv')
    mapper = CSVMapper(csv_path=csv_tender_path, release_type="tender")
    tender_context = mapper.get_coverage_context()

    td_context_pth = os.path.join(data_dir, 'tender_context.csv')
    test_td_context_df = pd.read_csv(td_context_pth)
    test_td_context_dict = test_td_context_df.squeeze().to_dict()

    for key in test_td_context_dict:
        new = tender_context[key]
        test = test_td_context_dict[key]
        assert new == test


def test_check_awards_coverage():

    csv_tender_path = os.path.join(data_dir, 'city-of-london-corporation-award_20200608-20200615.csv')
    mapper = CSVMapper(csv_path=csv_tender_path, release_type="award")
    award_context = mapper.get_coverage_context()

    aw_context_pth = os.path.join(data_dir, 'award_context.csv')
    test_aw_context = pd.read_csv(aw_context_pth)
    test_aw_context_dict = test_aw_context.squeeze().to_dict()

    for key in test_aw_context_dict:
        new = award_context[key]
        test = test_aw_context_dict[key]
        assert new == test
