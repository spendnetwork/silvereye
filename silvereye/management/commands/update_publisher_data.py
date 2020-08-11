"""
Command to create an generate publisher metrics
"""
import logging
import os

from django.core.management import BaseCommand

import silvereye
from bluetail.models import OCDSPackageData, OCDSReleaseJSON
from silvereye.models import Publisher

logger = logging.getLogger('django')

SILVEREYE_DIR = silvereye.__path__[0]


class Command(BaseCommand):
    help = "Generates publisher metrics for tenders"

    def handle(self, *args, **kwargs):
        packages = OCDSReleaseJSON.objects.all()
        sorted_packages = packages.order_by("package_data__publisher_name", "-package_data__supplied_data__created")
        publishers = sorted_packages.distinct("package_data__publisher_name")

        for pub in publishers:
            contact = pub.release_json["buyer"].get("contactPoint")
            if contact:
                Publisher.objects.update_or_create(
                    publisher_id=pub.package_data.publisher_name,
                    publisher_name=pub.package_data.publisher_name,
                    defaults={
                        "contact_name": contact.get("name", ""),
                        "contact_email": contact.get("email", ""),
                        "contact_telephone": contact.get("telephone", ""),
                    }
                )
