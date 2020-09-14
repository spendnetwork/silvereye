"""
Command to update publisher metrics from submitted files
"""
import logging

from django.core.management import BaseCommand

from silvereye.helpers import update_publisher_monthly_counts

logger = logging.getLogger('django')


class Command(BaseCommand):
    help = "Updates publisher metrics"

    def handle(self, *args, **kwargs):
        update_publisher_monthly_counts()
