"""
Generates a set of fake publisher metrics data
"""

from django.core.management import BaseCommand

from silvereye.models import PublisherMetrics

"""
publisher_id
publisher_name
count_lastmonth
count_last3months
count_last12months
average_lastmonth
average_last3months
average_last12months
"""

class Command(BaseCommand):
    help = "Generates fake PublisherMetric rows"

    def handle(self, *args, **kwargs):
        data = [
            ('borsetshire', 'Borsetshire Council', 9, 54, 243, 244600, 231900, 241440),
            ('dornwall', 'Dornwall Council', 6, 23, 154, 244500, 231800, 241441),
            ('bevon', 'Bevon Council', 5, 12, 113, 244400, 231700, 241442),
        ]
        for row in data:
            pm, created = PublisherMetrics.objects.get_or_create(
                publisher_id=row[0],
                publisher_name=row[1],
                defaults={
                    'count_lastmonth': row[2],
                    'count_last3months': row[3],
                    'count_last12months': row[4],
                    'average_lastmonth': row[5],
                    'average_last3months': row[6],
                    'average_last12months': row[7],
                }
            )
            if created:
                print("Created publisher metric for {}".format(row[0]))
            else:
                print("Found existing publisher metric for {}".format(row[0]))
