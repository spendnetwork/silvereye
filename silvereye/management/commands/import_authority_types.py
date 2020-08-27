"""
Command to import authority types from external sources
"""
import requests
import csv

from django.core.management import BaseCommand

from silvereye.models import AuthorityType


class Command(BaseCommand):
    help = "Imports lists of authority types from external sources"

    def handle(self, *args, **kwargs):
        csv_url = 'https://github.com/ajparsons/uk_local_authority_names_and_codes/raw/master/uk_local_authorities.csv'
        response = requests.get(csv_url)
        local_authorities = csv.DictReader(response.text.splitlines())
        for la in local_authorities:
            _, created = AuthorityType.objects.get_or_create(
                authority_name=la['official-name'],
                authority_type=la['local-authority-type-name'],
                source=csv_url,
            )
            if created:
                self.stdout.write(f"Created new AuthorityType for {la['official-name']}")
            else:
                self.stdout.write(f"Found existing AuthorityType for {la['official-name']}")
