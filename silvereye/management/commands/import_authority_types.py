"""
Command to import authority types from external sources
"""
import os

from django.core.management import BaseCommand
import pandas as pd
import numpy as np

import silvereye
from silvereye.models import AuthorityType

SILVEREYE_DIR = silvereye.__path__[0]


class Command(BaseCommand):
    help = "Imports lists of authority types from external sources"

    def handle(self, *args, **kwargs):

        csv_url = 'https://github.com/ajparsons/uk_local_authority_names_and_codes/raw/master/uk_local_authorities.csv'
        csv_path = os.path.join(SILVEREYE_DIR, "data", "uk_local_authorities.csv")
        df = pd.read_csv(csv_path)
        df = df.fillna("")
        # df = df.replace({np.nan:None})

        for i, la in df.iterrows():
            _, created = AuthorityType.objects.get_or_create(
                authority_name=la['official-name'],
                authority_type=la['local-authority-type-name'],
                source=csv_url,
            )
            if created:
                self.stdout.write(f"Created new AuthorityType for {la['official-name']}")
            else:
                self.stdout.write(f"Found existing AuthorityType for {la['official-name']}")
