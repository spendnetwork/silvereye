"""
This file is copied from `cove_ocds/views.py` and modified for Silvereye
"""
import copy

import functools
import json
import logging
import os
import re
import warnings
from collections import OrderedDict
from decimal import Decimal

from dateutil import parser
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render
from django.utils import translation
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _
from libcove.lib.common import get_spreadsheet_meta_data
from libcove.lib.converters import convert_json, convert_spreadsheet
from libcove.lib.exceptions import CoveInputDataError
from libcoveocds.common_checks import common_checks_ocds
from libcoveocds.config import LibCoveOCDSConfig
from libcoveocds.schema import SchemaOCDS
from strict_rfc3339 import validate_rfc3339

from bluetail.helpers import UpsertDataHelpers
from cove_ocds.lib.views import group_validation_errors
from silvereye.helpers import S3_helpers, sync_with_s3, prepare_simple_csv_validation_errors, \
    update_publisher_monthly_counts, convert_simple_csv_submission
from silvereye.models import FileSubmission, FieldCoverage
from silvereye.ocds_csv_mapper import CSVMapper

from cove_ocds.lib import exceptions
from cove_ocds.lib.ocds_show_extra import add_extra_fields

# Don't need to import this as we use our own modified function below
# from cove.views import explore_data_context

# But we do need some dependencies
from django.core.exceptions import ValidationError
from libcove.lib.tools import get_file_type as _get_file_type

logger = logging.getLogger(__name__)


def cove_web_input_error(func):
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except CoveInputDataError as err:
            return render(request, "error.html", context=err.context)

    return wrapper


# From libcoveweb
def get_file_name(file_name):
    if file_name is not None and '/' in file_name:
        file_name = file_name.split('/')[-1]
    return file_name


# From libcoveweb
# Updated to store/sync with S3 bucket
def explore_data_context(request, pk, get_file_type=None):
    if get_file_type is None:
        get_file_type = _get_file_type

    try:
        data = FileSubmission.objects.get(pk=pk)
        # Updated code to sync local storage to/from S3 storage
        if settings.STORE_OCDS_IN_S3:
            sync_with_s3(data)
    except (FileSubmission.DoesNotExist, ValidationError):  # Catches primary key does not exist and badly formed UUID
        try:
            if settings.STORE_OCDS_IN_S3:
                S3_helpers().retrieve_data_from_S3(pk)
                data = FileSubmission.objects.get(pk=pk)
        except (FileSubmission.DoesNotExist, ValidationError):  # Catches primary key does not exist and badly formed UUID
            logger.exception("Couldn't get data from S3: %s", pk)
            return {}, None, render(request, 'error.html', {
                'sub_title': _('Sorry, the page you are looking for is not available'),
                'link': 'index',
                'link_text': _('Go to Home page'),
                'msg': _("We don't seem to be able to find the data you requested.")
            }, status=404)


    file_type = get_file_type(data.original_file)
    original_file_path = data.original_file.path

    try:
        file_name = data.original_file.file.name
        if file_name.endswith('validation_errors-3.json'):
            raise PermissionError('You are not allowed to upload a file with this name.')
    except FileNotFoundError:
        return {}, None, render(request, 'error.html', {
            'sub_title': _('Sorry, the page you are looking for is not available'),
            'link': 'index',
            'link_text': _('Go to Home page'),
            'msg': _('The data you were hoping to explore no longer exists.\n\nThis is because all '
                     'data supplied to this website is automatically deleted after 7 days, and therefore '
                     'the analysis of that data is no longer available.')
        }, status=404)

    context = {
        'original_file': {
            'url': data.original_file.url,
            'size': data.original_file.size,
            'path': original_file_path,
        },
        'file_type': file_type,
        'file_name': get_file_name(file_name),
        'data_uuid': pk,
        'current_url': request.build_absolute_uri(),
        'source_url': data.source_url,
        'form_name': data.form_name,
        'created_datetime': data.created.strftime('%A, %d %B %Y %I:%M%p %Z'),
        'created_date': data.created.strftime('%A, %d %B %Y'),
        'created_time': data.created.strftime('%I:%M%p %Z'),
    }

    return (context, data, None)


@cove_web_input_error
def explore_ocds(request, pk):
    context, db_data, error = explore_data_context(request, pk)
    if error:
        return error

    lib_cove_ocds_config = LibCoveOCDSConfig()
    lib_cove_ocds_config.config["current_language"] = translation.get_language()
    lib_cove_ocds_config.config["schema_version_choices"] = settings.COVE_CONFIG[
        "schema_version_choices"
    ]
    lib_cove_ocds_config.config["schema_codelists"] = settings.COVE_CONFIG[
        "schema_codelists"
    ]

    upload_dir = db_data.upload_dir()
    upload_url = db_data.upload_url()
    file_name = db_data.original_file.file.name
    file_type = context["file_type"]

    post_version_choice = request.POST.get("version", lib_cove_ocds_config.config["schema_version"])
    replace = False
    validation_errors_path = os.path.join(upload_dir, "validation_errors-3.json")

    if file_type == "json":
        # open the data first so we can inspect for record package
        with open(file_name, encoding="utf-8") as fp:
            try:
                json_data = json.load(
                    fp, parse_float=Decimal, object_pairs_hook=OrderedDict
                )
            except ValueError as err:
                raise CoveInputDataError(
                    context={
                        "sub_title": _("Sorry, we can't process that data"),
                        "link": "index",
                        "link_text": _("Try Again"),
                        "msg": _(
                            format_html(
                                "We think you tried to upload a JSON file, but it is not well formed JSON."
                                '\n\n<span class="glyphicon glyphicon-exclamation-sign" aria-hidden="true">'
                                "</span> <strong>Error message:</strong> {}",
                                err,
                            )
                        ),
                        "error": format(err),
                    }
                )

            if not isinstance(json_data, dict):
                raise CoveInputDataError(
                    context={
                        "sub_title": _("Sorry, we can't process that data"),
                        "link": "index",
                        "link_text": _("Try Again"),
                        "msg": _(
                            "OCDS JSON should have an object as the top level, the JSON you supplied does not."
                        ),
                    }
                )

            version_in_data = json_data.get("version", "")
            db_data.data_schema_version = version_in_data
            select_version = post_version_choice or db_data.schema_version
            schema_ocds = SchemaOCDS(
                select_version=select_version,
                release_data=json_data,
                lib_cove_ocds_config=lib_cove_ocds_config,
            )

            if schema_ocds.missing_package:
                exceptions.raise_missing_package_error()
            if schema_ocds.invalid_version_argument:
                # This shouldn't happen unless the user sends random POST data.
                exceptions.raise_invalid_version_argument(post_version_choice)
            if schema_ocds.invalid_version_data:
                if isinstance(version_in_data, str) and re.compile(
                    "^\d+\.\d+\.\d+$"
                ).match(version_in_data):
                    exceptions.raise_invalid_version_data_with_patch(version_in_data)
                else:
                    if not isinstance(version_in_data, str):
                        version_in_data = "{} (it must be a string)".format(
                            str(version_in_data)
                        )
                    context["unrecognized_version_data"] = version_in_data

            if schema_ocds.version != db_data.schema_version:
                replace = True
            if schema_ocds.extensions:
                schema_ocds.create_extended_release_schema_file(upload_dir, upload_url)
            schema_url = schema_ocds.extended_schema_file or schema_ocds.release_schema_url

            if "records" in json_data:
                context["conversion"] = None
            else:
                # Replace the spreadsheet conversion only if it exists already.
                converted_path = os.path.join(upload_dir, "flattened")
                replace_converted = replace and os.path.exists(converted_path + ".xlsx")

                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore')  # flattentool uses UserWarning, so can't set a specific category

                    convert_json_context = convert_json(
                        upload_dir,
                        upload_url,
                        file_name,
                        lib_cove_ocds_config,
                        schema_url=schema_url,
                        replace=replace_converted,
                        request=request,
                        flatten=request.POST.get("flatten"),
                    )

                context.update(convert_json_context)

    else:
        # Use the lowest release pkg schema version accepting 'version' field
        metatab_schema_url = SchemaOCDS(
            select_version="1.1", lib_cove_ocds_config=lib_cove_ocds_config
        ).release_pkg_schema_url
        metatab_data = get_spreadsheet_meta_data(
            upload_dir, file_name, metatab_schema_url, file_type
        )
        if "version" not in metatab_data:
            metatab_data["version"] = "1.0"
        else:
            db_data.data_schema_version = metatab_data["version"]

        select_version = post_version_choice or db_data.schema_version
        schema_ocds = SchemaOCDS(
            select_version=select_version,
            release_data=metatab_data,
            lib_cove_ocds_config=lib_cove_ocds_config,
        )

        # Unlike for JSON data case above, do not check for missing data package
        if schema_ocds.invalid_version_argument:
            # This shouldn't happen unless the user sends random POST data.
            exceptions.raise_invalid_version_argument(post_version_choice)
        if schema_ocds.invalid_version_data:
            version_in_data = metatab_data.get("version")
            if re.compile("^\d+\.\d+\.\d+$").match(version_in_data):
                exceptions.raise_invalid_version_data_with_patch(version_in_data)
            else:
                context["unrecognized_version_data"] = version_in_data

        # Replace json conversion when user chooses a different schema version.
        if db_data.schema_version and schema_ocds.version != db_data.schema_version:
            replace = True

        if schema_ocds.extensions:
            schema_ocds.create_extended_release_schema_file(upload_dir, upload_url)
        schema_url = schema_ocds.extended_schema_file or schema_ocds.release_schema_url
        pkg_url = schema_ocds.release_pkg_schema_url

        if file_type != "csv":
            # ORIGINAL UNFLATTEN
            conversion_context = convert_spreadsheet(
                    upload_dir,
                    upload_url,
                    file_name,
                    file_type,
                    lib_cove_ocds_config,
                    schema_url=schema_url,
                    pkg_schema_url=pkg_url,
                    replace=replace,
            )
        else:
            # Convert Simple CSV to flat OCDS and return context

            conversion_context = convert_simple_csv_submission(
                db_data,
                lib_cove_ocds_config,
                schema_url,
                replace=replace,
            )

        context.update(conversion_context)

        with open(context["converted_path"], encoding="utf-8") as fp:
            json_data = json.load(
                fp, parse_float=Decimal, object_pairs_hook=OrderedDict
            )

    if replace:
        if os.path.exists(validation_errors_path):
            os.remove(validation_errors_path)

    context = common_checks_ocds(context, upload_dir, json_data, schema_ocds, cache=settings.CACHE_VALIDATION_ERRORS)

    if schema_ocds.json_deref_error:
        exceptions.raise_json_deref_error(schema_ocds.json_deref_error)

    schema_version = getattr(schema_ocds, "version", None)
    if schema_version:
        db_data.schema_version = schema_version
    if not db_data.rendered:
        db_data.rendered = True

    db_data.save()

    context.update(
        {
            "data_schema_version": db_data.schema_version,
            "first_render": not db_data.rendered,
            "validation_errors_grouped": group_validation_errors(
                context["validation_errors"]
            ),
        }
    )

    ocds_show_schema = SchemaOCDS()
    ocds_show_deref_schema = ocds_show_schema.get_release_schema_obj(deref=True)

    if "records" in json_data:
        template = "cove_ocds/explore_record.html"
        if hasattr(json_data, "get") and hasattr(json_data.get("records"), "__iter__"):
            context["records"] = json_data["records"]
        else:
            context["records"] = []
        if isinstance(json_data["records"], list) and len(json_data["records"]) < 100:
            context["ocds_show_data"] = ocds_show_data(
                json_data, ocds_show_deref_schema
            )
    else:
        template = "silvereye/explore_release.html"
        if hasattr(json_data, "get") and hasattr(json_data.get("releases"), "__iter__"):
            context["releases"] = json_data["releases"]
            if (
                isinstance(json_data["releases"], list)
                and len(json_data["releases"]) < 100
            ):
                context["ocds_show_data"] = ocds_show_data(
                    json_data, ocds_show_deref_schema
                )

            # Parse release dates into objects so the template can format them.
            for release in context["releases"]:
                if hasattr(release, "get") and release.get("date"):
                    if validate_rfc3339(release["date"]):
                        release["date"] = parser.parse(release["date"])
                    else:
                        release["date"] = None

                try:
                    trans_date = release["contracts"][0]["implementation"]["transactions"][0]["date"]
                    parsed_trans_date = parser.parse(trans_date)
                    release["contracts"][0]["implementation"]["transactions"][0]["date"] = parsed_trans_date
                except KeyError:
                    pass

            if context.get("releases_aggregates"):
                date_fields = [
                    "max_award_date",
                    "max_contract_date",
                    "max_release_date",
                    "max_tender_date",
                    "min_award_date",
                    "min_contract_date",
                    "min_release_date",
                    "min_tender_date",
                ]
                for field in date_fields:
                    if context["releases_aggregates"].get(field):
                        if validate_rfc3339(context["releases_aggregates"][field]):
                            context["releases_aggregates"][field] = parser.parse(
                                context["releases_aggregates"][field]
                            )
                        else:
                            context["releases_aggregates"][field] = None
        else:
            context["releases"] = []

    # Include field coverage report
    original_file_path = context["original_file"]["path"]
    mapper = CSVMapper(csv_path=original_file_path)
    db_data.notice_type = mapper.release_type
    db_data.save()
    coverage_context = mapper.get_coverage_context()
    context.update({
        "field_coverage": coverage_context,
    })

    ocds_validation_errors, simple_csv_errors = prepare_simple_csv_validation_errors(
        context["validation_errors"],
        mapper,
        coverage_context["required_fields_missing"]
    )

    context.update({
        "ocds_validation_errors": ocds_validation_errors,
        "simple_csv_errors": simple_csv_errors
    })

    # Silvereye: Insert OCDS data
    releases = context.get("releases")
    if releases:
        # If we don't have validation errors
        validation_errors_grouped = context["validation_errors_grouped"]
        if not validation_errors_grouped:
            json_string = json.dumps(
                json_data,
                indent=2,
                sort_keys=True,
                cls=DjangoJSONEncoder
            )
            UpsertDataHelpers().upsert_ocds_data(json_string, supplied_data=db_data)

            average_field_completion = coverage_context.get("average_field_completion")
            inst, created = FieldCoverage.objects.update_or_create(
                file_submission=db_data,
                defaults={
                    "tenders_field_coverage": average_field_completion if mapper.release_type == "tender" else None,
                    "awards_field_coverage": average_field_completion if mapper.release_type == "award" else None,
                    "spend_field_coverage": average_field_completion if mapper.release_type == "spend" else None,
                }
            )
            update_publisher_monthly_counts()

    return render(request, template, context)


# This should only be run when data is small.
def ocds_show_data(json_data, ocds_show_deref_schema):
    new_json_data = copy.deepcopy(json_data)
    add_extra_fields(new_json_data, ocds_show_deref_schema)
    return json.dumps(new_json_data, cls=DecimalEncoder)


# From stackoverflow:  https://stackoverflow.com/questions/1960516/python-json-serialize-a-decimal-object
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)
