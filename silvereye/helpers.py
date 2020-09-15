import json
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
import logging
import os
import re
from urllib.parse import urlparse, parse_qsl, urlencode

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import get_storage_class
import requests
from django.db import connections
from django.db.models import Sum, Avg
from django.db.models.functions import Coalesce
from django.utils.safestring import mark_safe

import silvereye
from silvereye.lib.converters import convert_csv
from silvereye.models import FileSubmission, FieldCoverage

logger = logging.getLogger(__name__)

SILVEREYE_DIR = silvereye.__path__[0]


class S3_helpers():
    def retrieve_data_from_S3(self, id):
        logger.info("Attempting to download file for SuppliedData from S3: %s", id)

        upsert_helper = UpsertDataHelpers()
        s3_storage = get_storage_class(settings.S3_FILE_STORAGE)()

        directories, filenames = s3_storage.listdir(name=id)

        for filename in filenames:
            original_file_path = os.path.join(id, filename)
            logger.info(f"Downloading {original_file_path}")
            filename_root = os.path.splitext(filename)[0]

            # Create FileSubmission entry
            supplied_data, created = FileSubmission.objects.update_or_create(
                id=id,
                defaults={
                    "current_app": "silvereye",
                    "original_file": original_file_path,
                }
            )

            # Extract created date from filename if possible
            try:
                filename_datetime = datetime.strptime(filename_root, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                supplied_data.created = filename_datetime
            except ValueError:
                logger.debug("Couldn't extract datetime from filename")

            supplied_data.save()
            sync_with_s3(supplied_data)

            # package_json_raw = s3_storage._open(original_file_path)
            # package_json_dict = json.load(package_json_raw)
            # package_json = json.dumps(package_json_dict)
            #
            # upsert_helper.upsert_ocds_data(package_json, supplied_data=supplied_data)


def sync_with_s3(supplied_data):
    logger.info("Syncing supplied_data original_file with S3")
    s3_storage = get_storage_class(settings.S3_FILE_STORAGE)()
    original_filename = supplied_data.original_file.name.split(os.path.sep)[1]
    original_file_path = supplied_data.original_file.path
    # Sync to S3
    if os.path.exists(original_file_path):
        if not s3_storage.exists(supplied_data.original_file.name):
            logger.info("Storing to S3: %s", supplied_data.original_file.name)
            local_file = supplied_data.original_file.read()
            # Temporarily change the storage for the original_file FileField to save to S3
            supplied_data.original_file.storage = s3_storage
            supplied_data.original_file.save(original_filename, ContentFile(local_file))
            # Put storage back to DEFAULT_FILE_STORAGE for
            supplied_data.original_file.storage = get_storage_class(settings.DEFAULT_FILE_STORAGE)()
    # Sync from S3 if not local
    if not os.path.exists(original_file_path):
        if s3_storage.exists(supplied_data.original_file.name):
            logger.info("Retrieving from S3: %s", supplied_data.original_file.name)
            # Switch to S3 storage and read file
            supplied_data.original_file.storage = s3_storage
            s3_file = supplied_data.original_file.read()
            # Switch storage back and save file locally
            supplied_data.original_file.storage = get_storage_class(settings.DEFAULT_FILE_STORAGE)()
            supplied_data.original_file.save(original_filename, ContentFile(s3_file))


class GoogleSheetHelpers():
    def get_sheet(self, url=""):
        # response = requests.get('https://docs.google.com/spreadsheet/ccc?key=0ArM5yzzCw9IZdEdLWlpHT1FCcUpYQ2RjWmZYWmNwbXc&output=csv')
        # XLSX download
        # response = requests.get('https://doc-0s-9k-docs.googleusercontent.com/docs/securesc/n0brkuvlm1o8v4u5up5nq9pasjli738t/e8277pb9tjvu5qsf4c9plmqjshmaadtj/1595943150000/07589777472805171581/07589777472805171581/1FWayBu0AogNhpCNdBUY8JYHHIHYIsTV2?e=download&h=03732756254954671626&authuser=0&nonce=k5isku8rmg6qc&user=07589777472805171581&hash=6qunlod35ocgdevm17se8e9s8k6s7pl2')
        # drive shared link
        # https://drive.google.com/file/d/1FWayBu0AogNhpCNdBUY8JYHHIHYIsTV2/view?usp=sharing
        response = requests.get('https://docs.google.com/spreadsheets/d/1Wkad_nigbS6xti8X0bzagfi8Hy5R2JvggtOMPQSvOpg/export?format=csv&gid=0')
        c = response.content
        return c

    def fix_url(self, url):
        if "docs.google.com/spreadsheets/" in url:
            # file_id = re.search(r"gid=([0-9]+)", parsed.fragment).group(1)

            if "xlsx" in url:
                url = "https://drive.google.com/uc?export=download&id=1FWayBu0AogNhpCNdBUY8JYHHIHYIsTV2"
                return url
            if "export" not in url:
                parsed = urlparse(url)
                if parsed.path.endswith("edit"):
                    gid = re.search(r"gid=([0-9]+)", parsed.fragment).group(1)
                    # guid = parsed.fragment.split("gid=")
                    parsed = parsed._replace(path=parsed.path.replace("edit", "export"))
                    # parsed.path = parsed.path.replace("edit", "export")
                    query = dict(parse_qsl(parsed.query))
                    query["format"] = "csv"
                    query["gid"] = gid
                    query2 = urlencode(query)
                    parsed = parsed._replace(query=query2)
                    parsed = parsed._replace(fragment="")
                    url_new = parsed.geturl()
                    return url_new
        return url


def get_published_release_metrics(release_queryset):
    count_tenders = release_queryset.filter(release_tag__contains="tender").count()
    count_awards = release_queryset.filter(release_tag__contains="award").count()
    count_spend = release_queryset.filter(release_tag__contains="spend").count()

    context = {
            "tenders_count": count_tenders,
            "awards_count": count_awards,
            "spend_count": count_spend,
    }
    return context


def update_publisher_monthly_counts():
    sql_path = os.path.join(SILVEREYE_DIR, "metrics", "monthly_counts.sql")

    with connections['default'].cursor() as cursor:
        sql = open(sql_path).read()
        logger.info(f"Executing metric sql from file {sql_path}")
        cursor.execute(sql)


class MetricHelpers():
    def __init__(self):
        self.get_values_func = self.period_counts

    def period_descriptions(self):
        return  {
            'current': 'this month',
            '1_month': 'last month',
            '3_month': 'last 3 months',
            '6_month': 'last 6 months',
            '12_month': 'last 12 months',
            'all': 'all time'
        }

    def comparison_descriptions(self):
        return {
            'preceding': 'preceding period',
            '1_year': 'last year',
            '2_year': 'two years ago'
        }

    def percentage_change_value(self, current, previous):
        raw_percent = (100 * (current - previous) / previous) if previous else 0
        return round(raw_percent)

    def period_counts(self, queryset, period_start, period_end):
        if not (period_start is None and period_end is None):
            queryset = queryset.filter(
                date__gte=period_start,
                date__lt=period_end
            )
        return queryset.aggregate(
            tenders=Coalesce(Sum('count_tenders'), 0),
            awards=Coalesce(Sum('count_awards'), 0),
            spend=Coalesce(Sum('count_spend'), 0)
        )

    def field_coverages(self, queryset, period_start, period_end):
        if not (period_start is None and period_end is None):
            queryset = queryset.filter(
                file_submission__created__gte=period_start,
                file_submission__created__lt=period_end
            )
        queryset = queryset.aggregate(
            tenders=Coalesce(Avg('tenders_field_coverage'), 0),
            awards=Coalesce(Avg('awards_field_coverage'), 0),
            spend=Coalesce(Avg('spend_field_coverage'), 0),
        )
        return queryset

    def period_data(self, queryset, period_start, period_end):
        period_counts = self.get_values_func(queryset, period_start, period_end)
        return {
            "counts": {
                "tenders": period_counts.get("tenders"),
                "awards": period_counts.get("awards"),
                "spend": period_counts.get("spend"),
            }
        }

    def comparison_data(self, queryset, comparison_start, comparison_end, period_counts):
        comparison_counts = self.get_values_func(queryset, comparison_start, comparison_end)

        return { "change": {
                    "tenders": round(period_counts.get("tenders") - comparison_counts.get("tenders"), 1),
                    "awards": round(period_counts.get("awards") - comparison_counts.get("awards"), 1),
                    "spend": round(period_counts.get("spend") - comparison_counts.get("spend"), 1),
                    },
                 "percentages": {
                    "tenders": self.percentage_change_value(period_counts.get("tenders"), comparison_counts.get("tenders")),
                    "awards": self.percentage_change_value(period_counts.get("awards"), comparison_counts.get("awards")),
                    "spend": self.percentage_change_value(period_counts.get("spend"), comparison_counts.get("spend")),
                    },
                 "counts": {
                    "tenders": comparison_counts.get("tenders"),
                    "awards": comparison_counts.get("awards"),
                    "spend": comparison_counts.get("spend"),
                    },
                }

    def metric_data(self, queryset, reference_date, period_option, comparison_option):
        data = {}

        period_start, period_end = self.period_bounds(reference_date=reference_date,
                                                      period_option=period_option)
        period_data = self.period_data(queryset, period_start, period_end)

        if period_option != 'all':
            period_data['comparison'] = {}
            comparison_start, comparison_end = self.comparison_bounds(period_start, period_end, period_option, comparison_option)
            period_data['comparison'] = self.comparison_data(queryset, comparison_start, comparison_end, period_data['counts'])
        return period_data

    def period_bounds(self, reference_date, period_option):
        if period_option == 'all':
            period_start = None
            period_end = None
        elif period_option == 'current':
            period_end = reference_date + relativedelta(days=1)
            period_start = reference_date.replace(day=1)
        else:
            period_span = self.parse_period_option(period_option)
            period_end = reference_date.replace(day=1)
            period_start = period_end - relativedelta(months=period_span)
        return (period_start, period_end)

    def comparison_bounds(self, period_start, period_end, period_option, comparison_option):
        if period_option == 'current':
            period_span = 1
            period_end = period_start.replace(day=1) + relativedelta(months=period_span)
        else:
            period_span = self.parse_period_option(period_option)
        if comparison_option == 'preceding':
            comparison_start = period_start - relativedelta(months=period_span)
            comparison_end = period_start
        else:
            comparison_span = self.parse_comparison_option(comparison_option)
            comparison_start = period_start - relativedelta(years=comparison_span)
            comparison_end = period_end - relativedelta(years=comparison_span)
        return (comparison_start, comparison_end)

    def parse_comparison_option(self, comparison_option):
        # 1_year
        # 2_year
        return int(comparison_option.split('_')[0])

    def parse_period_option(self, period_option):
        # 1_month
        # 3_month
        # 6_month
        # 12_month
        return int(period_option.split('_')[0])


def get_publisher_metrics_context(queryset=None, period_option='1_month', comparison_option='preceding'):
    if not queryset:
        return {}

    today = date_today()
    metric_helpers = MetricHelpers()
    context = metric_helpers.metric_data(queryset=queryset,
                                              reference_date=today,
                                              period_option=period_option,
                                              comparison_option=comparison_option)
    context["period_option"] = metric_helpers.period_descriptions()[period_option]
    context["comparison_option"] = metric_helpers.comparison_descriptions()[comparison_option]
    return context


def get_coverage_metrics_context(queryset=None, period_option='1_month', comparison_option='preceding'):

    if not queryset:
        return {}

    today = date_today()
    metric_helpers = MetricHelpers()
    if queryset.model == FieldCoverage:
        metric_helpers.get_values_func = metric_helpers.field_coverages
    context = metric_helpers.metric_data(
        queryset=queryset,
        reference_date=today,
        period_option=period_option,
        comparison_option=comparison_option)
    context["period_option"] = metric_helpers.period_descriptions()[period_option]
    context["comparison_option"] = metric_helpers.comparison_descriptions()[comparison_option]

    return context


def get_metric_options(request):
    period_option = request.GET.get('period', '1_month') or '1_month'
    comparison_option = request.GET.get('comparison', 'preceding') or 'preceding'
    return (period_option, comparison_option)


def date_today():
    return datetime.now().date()


def prepare_simple_csv_validation_errors(validation_errors, mapper, required_fields_missing=None):
    """
    Rename  OCDS uri headers to simple CSV headers in validation errors

    :param validation_errors:
    :param mapper:
    :param required_fields_missing:
    :return:
    """

    mapping_dict = {}
    for i, row in mapper.mappings_df.iterrows():
        if row["csv_header"]:
            mapping_dict[row["uri"]] = row["csv_header"]

    ocds_validation_errors = []
    simple_csv_errors = []
    for error_json, values in validation_errors:
        error_json_dict = json.loads(error_json)
        ocds_header = error_json_dict.get("header")
        if ocds_header in mapping_dict.keys():
            simple_csv_header = mapping_dict[ocds_header]
            error_json_dict["header"] = simple_csv_header
            error_json_dict["message"] = error_json_dict["message"].replace(f"'{ocds_header}'",
                                                                            f"'{simple_csv_header}'")
            error_json_dict["message_safe"] = error_json_dict["message_safe"].replace(f"<code>{ocds_header}</code>",
                                                                                      f"<code>{simple_csv_header}</code>")
            if error_json_dict["validator_value"] == "date-time":
                error_json_dict["message_safe"] = mark_safe(
                    'Incorrect date format. Use a standard date format such as ISO 8601: YYYY-MM-DDT00:00:00Z.')
            for i, value in enumerate(values):
                values[i]["header"] = simple_csv_header
                values[i]["row_number"] -= 1
            simple_csv_errors.append([error_json_dict, values])
        elif error_json_dict["validator"] != "required":
            ocds_validation_errors.append([error_json, values])
        # else:
        #     ocds_validation_errors.append([error_json, values])

    # Append extra "required" files as specified in the mappings
    for missing_csv_header, rows in required_fields_missing.items():
        # Only add new headers
        if missing_csv_header in [error[0].get("header") for error in simple_csv_errors]:
            continue
        else:
            simple_csv_errors.append([
                {
                    'assumption': None,
                    'error_id': None,
                    'header': f'{missing_csv_header}',
                    'header_extra': 'releases/[number]',
                    'message': f"'{missing_csv_header}' is missing but required",
                    'message_safe': f'<code>{missing_csv_header}</code> is missing but required',
                    'message_type': 'required',
                    'null_clause': '',
                    'path_no_number': 'releases',
                    'validator': 'required',
                    'validator_value': None
                },
                [{
                    'header': f'{missing_csv_header}',
                    'path': f'releases/{row}',
                    'row_number': row,
                    'sheet': 'releases'
                } for row in rows]
            ])

    return ocds_validation_errors, simple_csv_errors


def convert_simple_csv_submission(db_data, lib_cove_ocds_config, schema_url, file_type="csv", replace=True):
    # Silvereye CSV unflatten
    # Prepare base_json
    upload_dir = db_data.upload_dir()
    upload_url = db_data.upload_url()
    file_name = db_data.original_file.file.name

    base_json_path = os.path.join(upload_dir, "base.json")
    prepare_simple_csv_submission_base_json(base_json_path, db_data.publisher)
    conversion_context = convert_csv(
        upload_dir,
        upload_url,
        file_name,
        file_type,
        lib_cove_ocds_config,
        schema_url=schema_url,
        replace=replace,
        base_json_path=base_json_path
    )
    return conversion_context


def prepare_simple_csv_submission_base_json(base_json_path, publisher):
    base_json = {
        "version": "1.1",
        "publisher": {
            "name": publisher.publisher_name,
            "scheme": publisher.publisher_scheme,
            "uid": publisher.publisher_id,
        },
        "publishedDate": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        # "license": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/2/",
        # "publicationPolicy": "https://www.gov.uk/government/publications/open-contracting",
        "uri": "https://ocds-silvereye.herokuapp.com/"
    }
    with open(base_json_path, "w") as writer:
        json.dump(base_json, writer, indent=2)