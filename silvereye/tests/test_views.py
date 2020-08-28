from django.test import TestCase
from django.urls import reverse

from datetime import date

from silvereye.models import Publisher, PublisherMonthlyCounts

class HomeViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create some test data
        publisher_counts = [['Borsetshire', '2020-07-01', 5, 3, 0],
                            ['Borsetshire', '2020-06-01', 6, 2, 0],
                            ['Setborshire', '2020-07-01', 5, 22, 0],
                            ['Setborshire', '2020-06-01', 4, 21, 0]

        ]
        for publisher_name, date, count_tenders, count_awards, count_spend in publisher_counts:
            publisher, created = Publisher.objects.update_or_create(publisher_name = publisher_name)
            counts = PublisherMonthlyCounts.objects.create(publisher=publisher,
                                                           date=date,
                                                           count_tenders=count_tenders,
                                                           count_awards=count_awards,
                                                           count_spend=count_spend)

    def test_home_url_exists_at_desired_location(self):
        response = self.client.get('/publisher-hub/')
        self.assertEqual(response.status_code, 200)

    def test_sets_publisher_metrics_in_context(self):
        response = self.client.get(reverse('publisher-hub'))
        self.assertEqual(response.status_code, 200)
        expected_metrics = { 'counts': {'tenders': 10, 'awards': 25, 'spend': 0 },
                             'comparison': {
                                        'percentages': {'tenders': 0, 'awards': 8.7, 'spend': 0 },
                                        'counts': {'tenders': 10, 'awards': 23, 'spend': 0 },
                                        'change': {'tenders': 0, 'awards': 2, 'spend': 0 },
                                },
                             'period_option': 'Last month',
                             'comparison_option': 'preceding'
                            }
        self.assertDictEqual(response.context['publisher_metrics'], expected_metrics)
