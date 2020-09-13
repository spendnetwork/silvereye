"""
Command to create an generate publisher metrics
"""
import argparse
import sys
import zipfile
from datetime import datetime, timedelta
import json
import logging
import os
from os.path import join
import urllib.request
import shutil
from random import random

import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta
from django.core.files.base import ContentFile, File
from django.core.management import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.template.defaultfilters import slugify
from ocdskit.combine import combine_release_packages
from flattentool import unflatten
from pandas.errors import EmptyDataError

import silvereye
from bluetail.helpers import UpsertDataHelpers
from cove_ocds.views import convert_simple_csv_submission
from libcoveocds.config import LibCoveOCDSConfig
from silvereye.helpers import update_publisher_monthly_counts
from silvereye.ocds_csv_mapper import CSVMapper
from silvereye.models import Publisher, FileSubmission, FieldCoverage

logger = logging.getLogger('django')

SILVEREYE_DIR = silvereye.__path__[0]
METRICS_SQL_DIR = os.path.join(SILVEREYE_DIR, "metrics", "sql")
CF_DAILY_DIR = os.path.join(SILVEREYE_DIR, "data", "cf_daily_csv")
WORKING_DIR = os.path.join(CF_DAILY_DIR, "working_files")
SOURCE_DIR = os.path.join(WORKING_DIR, "source")
CLEAN_OUTPUT_DIR = join(WORKING_DIR, "cleaned")
SAMPLE_SUBMISSIONS_DIR = join(WORKING_DIR, "submissions")
CF_MAPPINGS_FILE = os.path.join(SILVEREYE_DIR, "data", "csv_mappings", "contracts_finder_mappings.csv")
OCDS_RELEASE_SCHEMA = join(SILVEREYE_DIR, "data", "OCDS", "1.1.4-release-schema.json")


def get_publisher_names():
    """
    Get a list of names of publishers who are expected to submit data
    """
    publishers = ['City of London Corporation',
                  'Crown Commercial Service',
                  'Devon County Council',
                  'Highways England',
                  'Leeds City Council',
                  'London Fire Commissioner',
                  'Newcastle City Council',
                  'Nottingham City Council',
                  'North Tyneside Council',
                  'Telford & Wrekin Council',
                  'London Borough of Hackney',
                  'London Borough of Enfield',
                  ]
    return publishers


def set_scheme(row):
    buyer_scheme = row.get('releases/0/buyer/identifier/scheme')
    if buyer_scheme and isinstance(buyer_scheme, str):
        return buyer_scheme
    else:
        return "GB-OO"


def create_uid(row):
    return slugify(row['publisher/name'])


def set_uid(row):
    buyer_id = row.get('releases/0/buyer/identifier/id')
    if buyer_id and isinstance(buyer_id, str):
        return buyer_id
    else:
        return slugify(row['publisher/name'])


def set_uri(row):
    buyer_uri = row.get('releases/0/buyer/identifier/uri')
    if buyer_uri and isinstance(buyer_uri, str):
        return buyer_uri
    else:
        return "http://www.example.com/" + row['publisher/uid']


def new_ocid_prefix(row):
    ocid = row['releases/0/ocid']
    ocid_prefix = get_ocid_prefix(ocid)
    uid = create_uid(row)
    new_ocid = [ord(char) - 96 for char in uid.replace('-', '')]
    new_ocid_prefix = 'ocds-' + ''.join(map(str, new_ocid))[0:6]
    return ocid.replace(ocid_prefix, new_ocid_prefix, 1)


def fix_contracts_finder_flat_CSV(df):
    """
    Process raw CF CSV:
        - Filter columns using headers in CF mappings file
        - fix array issue with tags
        - Use the first buyer name in the release as the publisher name and
          create example publisher attributes
    """
    cf_mapper = CSVMapper(mappings_file=CF_MAPPINGS_FILE)
    cols_list = cf_mapper.mappings_df["contracts_finder_daily_csv_path"].to_list()
    fixed_df = df[df.columns.intersection(cols_list)]
    fixed_df = fixed_df.rename(columns={
        'releases/0/tag/0': 'releases/0/tag'
    })

    # Create example publisher attributes
    fixed_df['publisher/name'] = fixed_df['releases/0/buyer/name']
    # fixed_df['publisher/scheme'] = fixed_df['releases/0/buyer/identifier/scheme']
    # fixed_df['publisher/uid'] = str(fixed_df['releases/0/buyer/identifier/id'])
    # fixed_df['publisher/scheme'] = "GB-OO"
    fixed_df['publisher/scheme'] = fixed_df.apply(lambda row: set_scheme(row), axis=1)
    fixed_df['publisher/uid'] = fixed_df.apply(lambda row: set_uid(row), axis=1)
    fixed_df['publisher/uri'] = fixed_df.apply(lambda row: set_uri(row), axis=1)
    fixed_df['releases/0/ocid'] = fixed_df.apply(lambda row: new_ocid_prefix(row), axis=1)
    fixed_df['releases/0/id'] = fixed_df.apply(lambda row: row['releases/0/id'].replace('ocds-b5fd17-', ''), axis=1)

    # CF does not move info from tender section to award section, so we need to do this
    # Set award title/desc from tender as CF don't include it
    fixed_df.loc[fixed_df['releases/0/tag'] == 'award', 'releases/0/awards/0/title'] = fixed_df['releases/0/tender/title']
    fixed_df.loc[fixed_df['releases/0/tag'] == 'award', 'releases/0/awards/0/description'] = fixed_df['releases/0/tender/description']
    fixed_df.loc[fixed_df['releases/0/tag'] == 'award', 'awards/0/contractPeriod/startDate'] = fixed_df['releases/0/tender/milestones/0/dueDate']
    fixed_df.loc[fixed_df['releases/0/tag'] == 'award', 'awards/0/contractPeriod/endDate'] = fixed_df['releases/0/tender/milestones/1/dueDate']

    # Copy items to awards
    for col in fixed_df.columns:
        if "tender/items" in col:
            fixed_df.loc[
                fixed_df['releases/0/tag'] == 'award', col.replace("releases/0/tender/", "releases/0/awards/0/")] = \
            fixed_df[col]

    return fixed_df


def unflatten_cf_data(json_file_path, last_published_date, load_data, output_dir):
    # Turn the fixed CF CSV into releases package JSON
    # Used in earlier work to test and debug the CF preprocessing pipeline, before the simple CSV conversion
    # Left here for debugging purposes
    schema = OCDS_RELEASE_SCHEMA
    unflatten(output_dir, output_name=json_file_path, input_format="csv", root_id="ocid", root_is_list=True,
              schema=schema)
    # Combine the packages from the file into one release package and
    # write it back to the file
    js = json.load(open(json_file_path))
    publisher = js[0]["publisher"]
    uri = js[0]["uri"]
    release_package = combine_release_packages(
        js,
        uri=uri,
        publisher=publisher,
        published_date=last_published_date,
        version='1.1'
    )
    release_package = json.dumps(
        release_package,
        indent=2,
        sort_keys=True,
        cls=DjangoJSONEncoder
    )
    release_file = open(json_file_path, "w")
    release_file.write(release_package)
    release_file.close()
    # Load the data from the file into the database
    if load_data:
        logger.info("Loading data from %s", json_file_path)
        js = json.load(open(json_file_path))
        # Extract the Contracts Finder ID from the uri of the first
        # release to use as an ID
        contracts_finder_id = os.path.splitext(os.path.split(uri)[1])[0]
        create_package_from_json(contracts_finder_id, js)


def get_ocid_prefix(ocid):
    """
    Return an 11 digit OCID prefix for a publisher from an OCID e.g
    ocds-b5fd17-e367ce01-4e9b-4692-8f89-1d1228dd9e04

    :param ocid: The OCID
    """
    return '-'.join(ocid.split('-')[:2])


def create_package_from_json(contracts_finder_id, package):
    """
    Create FileSubmission and OCDSPackageDataJSON records in the database for a
    Contracts Finder JSON OCDS release package

    :param contracts_finder_id: ID to use in constructing the FileSubmission ID
    :param package: JSON OCDS package
    """
    publisher = create_publisher_from_package_json(package)

    published_date = package["publishedDate"]
    logger.info("Creating FileSubmission %s uri %s date %s", publisher.publisher_name, contracts_finder_id, published_date)
    # Create FileSubmission entry
    supplied_data, created = FileSubmission.objects.update_or_create(
        id=contracts_finder_id,
        defaults={
            "current_app": "silvereye",
        }
    )
    supplied_data.publisher = publisher
    supplied_data.created = published_date
    supplied_data.original_file.save("release_package.json", ContentFile(json.dumps(package, indent=2)))
    supplied_data.save()

    json_string = json.dumps(
        package,
        indent=2,
        sort_keys=True,
        cls=DjangoJSONEncoder
    )
    UpsertDataHelpers().upsert_ocds_data(json_string, supplied_data)


def create_publisher_from_package_json(package):
    publisher = package["publisher"]
    publisher_name = publisher.get("name")
    publisher_id = publisher.get("uid")
    publisher_scheme = publisher.get("scheme")
    publisher_uri = publisher.get("uri")
    ocid_prefix = get_ocid_prefix(package["releases"][0]["ocid"])
    logger.info("Creating or updating Publisher %s (id %s)", publisher_name, publisher_id)
    publisher, created = Publisher.objects.update_or_create(
        publisher_name=publisher_name,
        defaults={
            "publisher_name": publisher_name,
            "publisher_id": publisher_id,
            "publisher_scheme": publisher_scheme,
            "uri": publisher_uri,
            "ocid_prefix": ocid_prefix
        }

    )
    return publisher


def get_date_boundaries(start_date, end_date, df, days=7, unflatten_cf_data=False):
    """
    Return an iterator of tuples of the start and end dates for a set of weekly
    periods that will include the period defined by the start and end date
    passed. If no start_date is passed, it is set using the earliest
    publishedDate in the dataframe, and similarly with end_date

    :param start_date: first date to be included in the weekly periods
    :param end_date: last date to be included in the weekly periods
    :param df: the data frame
    """
    if start_date is None:
        start_date = df['publishedDate'].min()
    else:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")

    if end_date is None:
        end_date = df['publishedDate'].max()
    else:
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    # define the start of the week that contains the start date
    start = start_date - timedelta(days=start_date.weekday())
    # define the start of the week after the week that contains the end date
    end = (end_date - timedelta(days=end_date.weekday())) + timedelta(days=days)
    # get a range of week starts
    starts = pd.date_range(start=start, end=end, freq='W-MON', tz="UTC")
    # get tuples of week starts and ends
    return zip(starts, starts[1:])


def process_contracts_finder_csv(publisher_names, start_date, end_date, options={}, file_path=None):
    """
    Load Contracts Finder API flat CSV output from the source directory,
    pre-process it and turn it into JSON. Group the data into publisher
    submission files if passed the publisher_submissions boolean option and
    load it into the database if passed the load_data boolean option

    :param publisher_names: List of names of publishers to preprocess
    :param start_date: first date on which data might appear
    :param end_date: last date on which data might appear
    :param options: Dictionary of options
    """
    publisher_submissions = options['publisher_submissions']
    load_data = options['load_data']
    source_data = []
    file_list = []

    # Prepare list of CSVs to process
    if file_path:
        file_list = [file_path]
    else:
        for file_name in os.listdir(SOURCE_DIR):
            if file_name.endswith(".csv"):
                source_file_path = join(SOURCE_DIR, file_name)
                if file_name < start_date.replace("-", "") or file_name > end_date.replace("-", ""):
                    continue
                else:
                    file_list.append(source_file_path)
                    file_list.sort()

    # Preprocess and merge all the CSV files into one dataframe
    for source_file_path in file_list:
        try:
            logger.info("Preprocessing %s", source_file_path)
            df = pd.read_csv(source_file_path, escapechar='\\')
            fixed_df = fix_contracts_finder_flat_CSV(df)
            fixed_df = fixed_df.replace({np.nan: None})
            fixed_df['publishedDate'] = pd.to_datetime(fixed_df['publishedDate'])
            source_data.append(fixed_df)
        except pd.errors.EmptyDataError:
            pass
        except:
            logger.exception("error preprocessing %s", source_file_path)

    source_df = pd.concat(source_data, ignore_index=True)

    # Used to create CF mappings
    # source_combined_path = os.path.join(WORKING_DIR, "combined.csv")
    # source_df.to_csv(source_combined_path, index=False)

    # Filter for publisher names
    if publisher_names:
        logger.info("Filtering for named publishers")
        named_publishers = source_df['publisher/name'].isin(publisher_names)
        source_df = source_df[named_publishers]

    if not start_date:
        file_name = os.path.basename(file_path)
        create_output_files(file_name, source_df, CLEAN_OUTPUT_DIR, load_data)
        return

    # Get the date boundaries to use for package files
    date_boundaries = get_date_boundaries(start_date, end_date, source_df)

    # Filter the data according to those boundaries
    for start, end in date_boundaries:
        period_dir = join(CLEAN_OUTPUT_DIR, start.strftime("%Y%m%d") + "-" + end.strftime("%Y%m%d"))
        os.makedirs(period_dir)
        boundary_mask = (source_df['publishedDate'] > start) & (source_df['publishedDate'] <= end)
        period_df = source_df.loc[boundary_mask]

        # If grouping by publisher, create the output files per publisher,
        # otherwise create a combined file
        if publisher_submissions:
            for publisher_name in period_df['publisher/name'].unique():
                publisher_df = period_df[period_df['publisher/name'] == publisher_name]
                directory_name = slugify(publisher_name)
                create_output_files(directory_name, publisher_df, period_dir, load_data)
        else:
            create_output_files('all', period_df, period_dir, load_data)


# Augment award with transaction
def augment_award_row_with_spend(row):
    row["releases/0/tag"] = "implementation"
    # Change IDs
    row["releases/0/ocid"] = row["releases/0/ocid"] + "_trans1"
    row["releases/0/id"] = row["releases/0/id"] + "_trans1"
    # Set published date some time later than award
    days_between_publishing_award_and_spend = int(random() * 10) + 10
    award_pub_datetime = datetime.strptime(row["releases/0/date"], '%Y-%m-%dT%H:%M:%SZ')
    trans_pub_datetime = datetime.strftime(
        award_pub_datetime + relativedelta(days=days_between_publishing_award_and_spend), '%Y-%m-%dT%H:%M:%SZ')
    row["releases/0/date"] = trans_pub_datetime
    row["publishedDate"] = trans_pub_datetime
    # Set Transaction date
    days_between_awarded_date_and_trans_date = int(random() * 10) + 10
    awarded_datetime = datetime.strptime(row["releases/0/awards/0/date"], '%Y-%m-%dT%H:%M:%SZ')
    trans_datetime = datetime.strftime(awarded_datetime + relativedelta(days=days_between_awarded_date_and_trans_date),
                                       '%Y-%m-%dT%H:%M:%SZ')
    row["releases/0/contracts/0/implementation/transactions/0/date"] = trans_datetime
    # Copy award value to transaction
    row["releases/0/contracts/0/implementation/transactions/0/value/amount"] = row["releases/0/awards/0/value/amount"]
    row["releases/0/contracts/0/implementation/transactions/0/value/currency"] = row["releases/0/awards/0/value/currency"]
    # Copy items to contract
    for col, value in row.items():
        if "tender/items" in col:
            row[col.replace("releases/0/tender/", "releases/0/contracts/0/")] = row[col]

    uri = row["uri"]
    contracts_finder_id = os.path.splitext(os.path.split(uri)[1])[0]
    spend_contracts_finder_id = contracts_finder_id[:-4] + "1234"
    row["uri"] = row["uri"].replace(contracts_finder_id, spend_contracts_finder_id)

    return row


def create_output_files(name, df, parent_directory, load_data, unflatten_contracts_finder_data=False):
    """
    Create a set of JSON format release package files from the DataFrame
    supplied for the releases where the type is tender or award. Load the data
    into the database if the load_data param is True.

    :param name: Name of the directory to create
    :param df: DataFrame containing the data
    :param parent_directory: Path to the parent directory to create the files
    :param load_data: Boolean indicating that the data should be loaded
    """
    release_types = ['tender',
                     'award',
                     'spend'
                     ]
    for release_type in release_types:
        logger.info("Creating output files for %s %s", name, release_type)

        release_name = name + "-" + release_type
        output_dir = join(parent_directory, release_name)
        os.makedirs(output_dir)
        json_file_path = join(output_dir, release_name + ".json")

        # Filter the DataFrame
        if release_type == "spend":
            # Use award data and add fake spend
            df_release_type = df[df['releases/0/tag'] == "award"]
            spend_df = pd.DataFrame()
            for i, row in df_release_type.iterrows():
                rowdf = df_release_type.loc[[i]]
                new_row_df = rowdf.apply(augment_award_row_with_spend, axis=1)
                spend_df = spend_df.append(new_row_df)
            if not df_release_type.empty:
                df_release_type = spend_df.loc[spend_df["publishedDate"] < str(datetime.now())]
        else:
            df_release_type = df[df['releases/0/tag'] == release_type]

        if df_release_type.shape[0] > 0:
            csv_file_name = release_name + ".csv"
            csv_file_path = join(output_dir, csv_file_name)

            last_published_date = df_release_type['publishedDate'].max()

            # Write the DataFrame to a CSV
            df_release_type.to_csv(open(csv_file_path, "w"), index=False, header=True)

            # Create fake simple submission CSV
            period_dir_name = os.path.basename(parent_directory)
            simple_csv_file_name = f"{release_name}_{period_dir_name}.csv"
            simple_csv_file_path = join(SAMPLE_SUBMISSIONS_DIR, simple_csv_file_name)
            cf_mapper = CSVMapper(mappings_file=CF_MAPPINGS_FILE)
            ocds_1_1_release_df = cf_mapper.convert_cf_to_1_1(df_release_type)
            mapper = CSVMapper(release_type=release_type)
            simple_csv_df = mapper.output_simple_csv(ocds_1_1_release_df)
            simple_csv_df.to_csv(open(simple_csv_file_path, "w"), index=False, header=True)

            # Upload simple CSV to DB
            if load_data:
                try:
                    publisher_name = df_release_type.iloc[0]["publisher/name"]
                    publisher_scheme = df_release_type.iloc[0]["publisher/scheme"]
                    publisher_id = df_release_type.iloc[0]["publisher/uid"]
                    publisher_uri = df_release_type.iloc[0]["publisher/uri"]
                    ocid_prefix = get_ocid_prefix(df_release_type.iloc[0]["releases/0/ocid"])

                    # helpers.SimpleSubmissionHelpers().load_simple_csv_into_database(simple_csv_df, publisher)
                    # Load data from Simple CSV
                    logger.info("Creating or updating Publisher %s (id %s)", publisher_name, publisher_id)
                    contact_name = df_release_type.iloc[0]["releases/0/buyer/contactPoint/name"]
                    contact_email = df_release_type.iloc[0]["releases/0/buyer/contactPoint/email"]
                    contact_telephone = df_release_type.iloc[0]["releases/0/buyer/contactPoint/telephone"]

                    publisher, created = Publisher.objects.update_or_create(
                        publisher_name=publisher_name,
                        defaults={
                            "publisher_name": publisher_name,
                            "publisher_id": publisher_id,
                            "publisher_scheme": publisher_scheme,
                            "uri": publisher_uri,
                            "ocid_prefix": ocid_prefix,
                            "contact_name": contact_name if contact_name else "",
                            "contact_email": contact_email if contact_email else "",
                            "contact_telephone": contact_telephone if contact_telephone else "",
                        }
                    )

                    published_date = df_release_type.iloc[0]["publishedDate"]

                    uri = df_release_type.iloc[0]["uri"]
                    contracts_finder_id = os.path.splitext(os.path.split(uri)[1])[0]

                    logger.info("Creating FileSubmission %s uri %s date %s", publisher.publisher_name, contracts_finder_id, published_date)
                    # Create FileSubmission entry
                    supplied_data, created = FileSubmission.objects.update_or_create(
                        id=contracts_finder_id,
                        defaults={
                            "current_app": "silvereye",
                            "notice_type": mapper.release_type,
                        }
                    )
                    supplied_data.publisher = publisher
                    supplied_data.created = published_date
                    if supplied_data.original_file and os.path.exists(supplied_data.original_file.path):
                        os.remove(supplied_data.original_file.path)
                    supplied_data.original_file.save(simple_csv_file_name, File(open(simple_csv_file_path)))
                    supplied_data.save()

                    # Store field coverage
                    mapper = CSVMapper(csv_path=simple_csv_file_path)
                    coverage_context = mapper.get_coverage_context()
                    average_field_completion = coverage_context.get("average_field_completion")
                    inst, created = FieldCoverage.objects.update_or_create(
                        file_submission=supplied_data,
                        defaults={
                            "tenders_field_coverage": average_field_completion if mapper.release_type == "tender" else None,
                            "awards_field_coverage": average_field_completion if mapper.release_type == "award" else None,
                            "spend_field_coverage": average_field_completion if mapper.release_type == "spend" else None,
                        }
                    )

                    lib_cove_ocds_config = LibCoveOCDSConfig()

                    conversion_context = convert_simple_csv_submission(
                        supplied_data,
                        lib_cove_ocds_config,
                        OCDS_RELEASE_SCHEMA
                    )
                    converted_path = conversion_context.get("converted_path")
                    UpsertDataHelpers().upsert_ocds_data(converted_path, supplied_data)
                except:
                    logger.exception("Error loading data for %s in %s", name, parent_directory)

            if unflatten_contracts_finder_data:
                unflatten_cf_data(json_file_path, last_published_date, load_data, output_dir)


def remake_dir(directory):
    """
    Delete and recreate a directory

    :param directory: Directory to recreate
    """
    shutil.rmtree(directory, ignore_errors=True)
    os.makedirs(directory)


class Command(BaseCommand):
    help = "Inserts Contracts Finder data using Flat CSV OCDS from the CF API.\nhttps://www.contractsfinder.service.gov.uk/apidocumentation/Notices/1/GET-Harvester-Notices-Data-CSV"

    def add_arguments(self, parser):
        parser.add_argument("--start_date", default=argparse.SUPPRESS, help="Import from date. YYYY-MM-DD")
        parser.add_argument("--end_date", default=argparse.SUPPRESS, help="Import to date. YYYY-MM-DD")
        parser.add_argument("--file_path", type=str, help="File path to CSV data to insert.")
        parser.add_argument("--publisher_submissions", action='store_true',
                            help="Group data into publisher submissions")
        parser.add_argument("--load_data", action='store_true', help="Load data into database")

    def handle(self, *args, **kwargs):

        publisher_names = get_publisher_names()
        remake_dir(SOURCE_DIR)
        remake_dir(CLEAN_OUTPUT_DIR)
        remake_dir(SAMPLE_SUBMISSIONS_DIR)
        file_path = kwargs.get("file_path")

        options = {
            'publisher_submissions': kwargs.get("publisher_submissions"),
            'load_data': kwargs.get("load_data")
        }

        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date", datetime.today().strftime("%Y-%m-%d"))
        if file_path:
            logger.info("Copying data from %s", file_path)
            if file_path.endswith(".zip"):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(SOURCE_DIR)
                file_path = None
            elif file_path.endswith(".csv"):
                shutil.copy(file_path, SOURCE_DIR)
        elif start_date:
            daterange = pd.date_range(start_date, end_date)
            logger.info("Downloading Contracts Finder data from %s to %s", start_date, end_date)
            for date in daterange:
                try:
                    date_string = f"{date.year}/{date.month:02}/{date.day:02}"
                    save_path = join(SOURCE_DIR, slugify(date_string) + ".csv")
                    url = f"https://www.contractsfinder.service.gov.uk/Harvester/Notices/Data/CSV/{date_string}"
                    if not os.path.exists(save_path):
                        urllib.request.urlretrieve(url, save_path)
                    logger.info("Downloading URL: %s", url)
                except TypeError:
                    logger.exception("Error with URL: %s", url)
        else:
            self.print_help('manage.py', '<your command name>')
            sys.exit()

        process_contracts_finder_csv(publisher_names, start_date, end_date, options, file_path)

        # Update publisher metrics
        update_publisher_monthly_counts()
