from django.test import TestCase
from django.urls import reverse

import datetime
from datetime import date

from django.db.models import Sum
from django.db.models.functions import Coalesce

from silvereye.models import Publisher, PublisherMonthlyCounts
from silvereye.helpers import MetricHelpers


class MetricHelpersTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.metric_helpers = MetricHelpers()
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


    def compare_bounds(self, params):

        date_types = ['reference_date', 'period_start', 'period_end', 'comparison_start', 'comparison_end']
        for date_type in date_types:
            params[date_type] = datetime.datetime.strptime(params[date_type], '%Y-%m-%d').date()
        expected_period = (params['period_start'], params['period_end'])
        expected_comparison = (params['comparison_start'], params['comparison_end'])
        self.assertEqual(self.metric_helpers.period_bounds(reference_date=params['reference_date'],
                                                   period_option=params['period_option']), expected_period)
        self.assertEqual(self.metric_helpers.comparison_bounds(period_start=params['period_start'],
                                                               period_end=params['period_end'],
                                                               period_option=params['period_option'],
                                                               comparison_option=params['comparison_option']), expected_comparison)
    def test_setting_one_month_period_preceding_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-07-01',
                  'period_end': '2020-08-01',
                  'comparison_start': '2020-06-01',
                  'comparison_end': '2020-07-01',
                  'period_option': '1_month',
                  'comparison_option': 'preceding'}
        self.compare_bounds(params)

    def test_setting_three_month_period_preceding_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-05-01',
                  'period_end': '2020-08-01',
                  'comparison_start': '2020-02-01',
                  'comparison_end': '2020-05-01',
                  'period_option': '3_month',
                  'comparison_option': 'preceding'}
        self.compare_bounds(params)

    def test_setting_six_month_period_preceding_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-02-01',
                  'period_end': '2020-08-01',
                  'comparison_start': '2019-08-01',
                  'comparison_end': '2020-02-01',
                  'period_option': '6_month',
                  'comparison_option': 'preceding'}
        self.compare_bounds(params)

    def test_setting_current_period_preceding_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-08-01',
                  'period_end': '2020-08-28',
                  'comparison_start': '2020-07-01',
                  'comparison_end': '2020-08-01',
                  'period_option': 'current',
                  'comparison_option': 'preceding'}
        self.compare_bounds(params)

    def test_setting_one_month_period_previous_year_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-07-01',
                  'period_end': '2020-08-01',
                  'comparison_start': '2019-07-01',
                  'comparison_end': '2019-08-01',
                  'period_option': '1_month',
                  'comparison_option': '1_year'}
        self.compare_bounds(params)


    def test_setting_three_month_period_previous_year_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-05-01',
                  'period_end': '2020-08-01',
                  'comparison_start': '2019-05-01',
                  'comparison_end': '2019-08-01',
                  'period_option': '3_month',
                  'comparison_option': '1_year'}
        self.compare_bounds(params)

    def test_setting_six_month_period_previous_year_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-02-01',
                  'period_end': '2020-08-01',
                  'comparison_start': '2019-02-01',
                  'comparison_end': '2019-08-01',
                  'period_option': '6_month',
                  'comparison_option': '1_year'}
        self.compare_bounds(params)

    def test_setting_current_period_previous_year_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-08-01',
                  'period_end': '2020-08-28',
                  'comparison_start': '2019-08-01',
                  'comparison_end': '2019-09-01',
                  'period_option': 'current',
                  'comparison_option': '1_year'}
        self.compare_bounds(params)

    def test_setting_one_month_period_two_year_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-07-01',
                  'period_end': '2020-08-01',
                  'comparison_start': '2018-07-01',
                  'comparison_end': '2018-08-01',
                  'period_option': '1_month',
                  'comparison_option': '2_year'}
        self.compare_bounds(params)


    def test_setting_three_month_period_two_year_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-05-01',
                  'period_end': '2020-08-01',
                  'comparison_start': '2018-05-01',
                  'comparison_end': '2018-08-01',
                  'period_option': '3_month',
                  'comparison_option': '2_year'}
        self.compare_bounds(params)

    def test_setting_six_month_period_two_year_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-02-01',
                  'period_end': '2020-08-01',
                  'comparison_start': '2018-02-01',
                  'comparison_end': '2018-08-01',
                  'period_option': '6_month',
                  'comparison_option': '2_year'}
        self.compare_bounds(params)

    def test_setting_current_period_two_year_comparison_bounds(self):
        params = {'reference_date': '2020-08-28',
                  'period_start': '2020-08-01',
                  'period_end': '2020-08-28',
                  'comparison_start': '2018-08-01',
                  'comparison_end': '2018-09-01',
                  'period_option': 'current',
                  'comparison_option': '2_year'}
        self.compare_bounds(params)

    def compare_period_data(self, period_start, period_end, expected_data):
        queryset = PublisherMonthlyCounts.objects.all()
        period_start =  datetime.datetime.strptime(period_start, '%Y-%m-%d').date()
        period_end =  datetime.datetime.strptime(period_end, '%Y-%m-%d').date()
        period_data = self.metric_helpers.period_data(queryset, period_start, period_end)
        self.assertEqual(period_data, expected_data)

    def test_getting_period_data(self):
        expected_data = {
                     "counts": {
                        "tenders": 10,
                        "awards": 25,
                        "spend": 0,
                        }
                    }
        self.compare_period_data('2020-07-01', '2020-08-01', expected_data)

    def test_getting_comparison_data(self):
        queryset = PublisherMonthlyCounts.objects.all()
        period_counts = queryset\
        .filter(date__gte=date(2020, 7, 1), date__lt=date(2020, 8, 1))\
        .aggregate(tenders=Coalesce(Sum('count_tenders'), 0), awards=Coalesce(Sum('count_awards'), 0), spend=Coalesce(Sum('count_spend'), 0))
        expected_data = {
            'change': {'awards': 2, 'spend': 0, 'tenders': 0},
                       'counts': {'awards': 23, 'spend': 0, 'tenders': 10},
                       'percentages': {'awards': 8.7, 'spend': 0, 'tenders': 0}}
        actual = self.metric_helpers.comparison_data(queryset, date(2020, 6, 1), date(2020, 7, 1), period_counts)
        self.assertEqual(actual, expected_data)
