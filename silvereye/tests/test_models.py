from django.conf import settings
from django.test import TestCase

from cove.input.models import SuppliedData

from silvereye.models import FileSubmission, Publisher

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

      supplied_data = SuppliedData.objects.get(id=1)
      self.assertEqual(supplied_data.filesubmission.publisher, publisher)
