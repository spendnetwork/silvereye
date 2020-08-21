import os

import pytest
from django.conf import settings
from django.test import TestCase

from silvereye.models import FileSubmission, Publisher

TESTS_DIR = os.path.dirname(os.path.realpath(__file__))


class FileSubmissionTestCase(TestCase):
    def setUp(self):
        supplied_data = FileSubmission.objects.create(id=1)

    def test_creation(self):
        supplied_data = FileSubmission.objects.get(id=1)
        self.assertIsNotNone(supplied_data.filesubmission)

    def test_saving(self):
        supplied_data = FileSubmission.objects.get(id=1)
        publisher = Publisher.objects.create(publisher_name='A Publisher')
        supplied_data.publisher = publisher
        supplied_data.save()

        supplied_data = FileSubmission.objects.get(id=1)
        self.assertEqual(supplied_data.publisher, publisher)


@pytest.mark.xfail
@pytest.mark.django_db
def test_get_file_from_s3(client):
    # resp = client.get('/data/03bc9b8d-0874-442c-b4aa-10f7ef872249')
    resp = client.get('/data/testfile')
    h = resp.content.decode()
    assert resp.status_code == 200
