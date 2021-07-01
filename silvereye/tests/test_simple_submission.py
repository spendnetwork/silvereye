import os

import pytest
from django.test import Client
from django.urls import reverse

from silvereye.helpers import GoogleSheetHelpers
from silvereye.models import Publisher, FileSubmission

TESTS_DIR = os.path.dirname(os.path.realpath(__file__))


class TestGoogleSheetHelpers():
    GShelper = GoogleSheetHelpers()

    def test_get_sheet(self):
        c = self.GShelper.get_sheet()
        assert c

    def test_fix_url(self):
        # CSV URL
        url = "https://docs.google.com/spreadsheets/d/1Wkad_nigbS6xti8X0bzagfi8Hy5R2JvggtOMPQSvOpg/edit#gid=0"
        fixed_url = self.GShelper.fix_url(url)
        assert fixed_url == "https://docs.google.com/spreadsheets/d/1Wkad_nigbS6xti8X0bzagfi8Hy5R2JvggtOMPQSvOpg/export?format=csv&gid=0"

        # XLSX
        # url = "https://docs.google.com/spreadsheets/d/1FWayBu0AogNhpCNdBUY8JYHHIHYIsTV2/edit#gid=1932706439"
        # url = "https://docs.google.com/spreadsheets/d/1FWayBu0AogNhpCNdBUY8JYHHIHYIsTV2/export?format=xlsx&id=1FWayBu0AogNhpCNdBUY8JYHHIHYIsTV2"
        # fixed_url = self.GShelper.fix_url(url)
        # assert fixed_url == "https://docs.google.com/spreadsheets/d/1Wkad_nigbS6xti8X0bzagfi8Hy5R2JvggtOMPQSvOpg/export?format=csv&gid=0"
        # # Google sheet as XLSX
        # url = "https://docs.google.com/spreadsheets/d/1Wkad_nigbS6xti8X0bzagfi8Hy5R2JvggtOMPQSvOpg/export?format=xlsx&id=1Wkad_nigbS6xti8X0bzagfi8Hy5R2JvggtOMPQSvOpg"


@pytest.fixture()
def publisher():
    publisher = Publisher.objects.create(
        publisher_name='Publisher1',
    )
    return publisher


@pytest.mark.django_db
def test_upload(publisher, simple_csv_submission_path):
    c = Client()
    path = os.path.join(TESTS_DIR, "fixtures/CSV_input/input.csv")
    with open(path) as fp:
        resp = c.post('/review/', {
            'original_file': fp,
            'publisher_id': publisher.id,
        })
    h = resp.content.decode()
    assert resp.status_code == 302


@pytest.mark.django_db
def test_upload_follow(publisher, simple_csv_submission_path):
    c = Client()
    with open(simple_csv_submission_path) as fp:
        resp = c.post(
            '/review/',
            {
                'original_file': fp,
                'publisher_id': publisher.id,
            },
            follow=True
        )
    h = resp.content.decode()
    assert resp.status_code == 200


@pytest.mark.django_db
def test_missing_instance_pk(publisher):
    c = Client()
    path = os.path.join(TESTS_DIR, "fixtures/CSV_input/input.csv")
    with open(path) as fp:
        resp = c.post('/review/', {
            'original_file': fp,
            'publisher_id': publisher.id,
        },
                      follow=True
                      )
    h = resp.content.decode()
    assert resp.status_code == 200
    id = resp


@pytest.mark.django_db
def test_upload_xlsx(publisher):
    c = Client()
    path = os.path.join(TESTS_DIR, "fixtures/XLSX_submission/spreadsheet_with_meta.xlsx")
    with open(path, "rb") as fp:
        resp = c.post(
            path=reverse('index'),
            data={
                'original_file': fp,
                'publisher_id': publisher.id,
            },
            # follow=True
        )
    h = resp.content.decode()
    assert resp.status_code == 302
