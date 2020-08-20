"""
Command to create an generate publisher metrics
"""
import argparse
import sys
from datetime import datetime, timedelta
import json
import logging
import os
import shutil
from os.path import join
import urllib.request
import shutil

import pandas as pd
from django.core.files.base import ContentFile
from django.core.management import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.template.defaultfilters import slugify
from ocdskit.combine import combine_release_packages
from flattentool import unflatten

import silvereye
from bluetail.helpers import UpsertDataHelpers
from silvereye.ocds_csv_mapper import CSVMapper
from silvereye.models import Publisher, FileSubmission

logger = logging.getLogger('django')

SILVEREYE_DIR = silvereye.__path__[0]
METRICS_SQL_DIR = os.path.join(SILVEREYE_DIR, "metrics", "sql")
CF_DAILY_DIR = os.path.join(SILVEREYE_DIR, "data", "cf_daily_csv")
WORKING_DIR = os.path.join(CF_DAILY_DIR, "working_files")
SOURCE_DIR = os.path.join(WORKING_DIR, "source")
CLEAN_OUTPUT_DIR = join(WORKING_DIR, "cleaned")
SAMPLE_SUBMISSIONS_DIR = join(WORKING_DIR, "submissions")

HEADERS_LIST = join(CF_DAILY_DIR, "headers_min.txt")
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
                  'Telford & Wrekin Council'
                  ]
    return publishers

def create_uid(row):
    return slugify(row['publisher/name'])

def create_uri(row):
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
        - Filter columns using headers in HEADERS_LIST file
        - fix array issue with tags
        - Use the first buyer name in the release as the publisher name and
          create example publisher attributes
    """
    cols_list = open(HEADERS_LIST).readlines()
    cols_list = [x.strip() for x in cols_list]
    fixed_df = df[df.columns.intersection(cols_list)]
    fixed_df = fixed_df.rename(columns={
        'releases/0/tag/0': 'releases/0/tag'
    })

    # Create example publisher attributes
    fixed_df['publisher/name'] = fixed_df['releases/0/buyer/name']
    fixed_df['publisher/scheme'] = "Example Publisher Scheme"
    fixed_df['publisher/uid'] = fixed_df.apply(lambda row: create_uid(row), axis=1)
    fixed_df['publisher/uri'] = fixed_df.apply(lambda row: create_uri(row), axis=1)
    fixed_df['releases/0/ocid'] = fixed_df.apply(lambda row: new_ocid_prefix(row), axis=1)

    # CF does not move info from tender section to award section, so we need to do this
    # Set award title/desc from tender as CF don't include it
    fixed_df.loc[fixed_df['releases/0/tag'] == 'award', 'releases/0/awards/0/title'] = fixed_df['releases/0/tender/title']
    fixed_df.loc[fixed_df['releases/0/tag'] == 'award', 'releases/0/awards/0/description'] = fixed_df['releases/0/tender/description']
    # Copy items to awards
    for col in fixed_df.columns:
        if "tender/items" in col:
            new_col = col.replace("releases/0/tender/", "releases/0/awards/0/")
            fixed_df[new_col] = fixed_df[col]


    return fixed_df

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
    published_date = package["publishedDate"]
    publisher = package["publisher"]
    publisher_name = publisher.get("name")
    publisher_id = publisher.get("uid")
    publisher_scheme = publisher.get("scheme")
    publisher_uri = publisher.get("uri")

    ocid_prefix = get_ocid_prefix(package["releases"][0]["ocid"])

    logger.info("Creating or updating Publisher %s (id %s)", publisher_name, publisher_id)

    publisher, created = Publisher.objects.update_or_create(
            publisher_scheme=publisher_scheme,
            publisher_id=publisher_id,
            defaults={
                "publisher_name": publisher_name,
                "publisher_id": publisher_id,
                "publisher_scheme": publisher_scheme,
                "uri": publisher_uri,
                "ocid_prefix": ocid_prefix
            }

        )

    logger.info("Creating FileSubmission %s uri %s date %s", publisher_name, contracts_finder_id, published_date)
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


def get_date_boundaries(start_date, end_date, df, days=7):
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


def process_contracts_finder_csv(publisher_names, start_date, end_date, options={}):
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

    # Preprocess and merge all the CSV files into one dataframe
    for file_name in os.listdir(SOURCE_DIR):
        if file_name.endswith(".csv"):
            try:
                logger.info("Preprocessing %s", file_name)
                df = pd.read_csv(join(SOURCE_DIR, file_name))
                fixed_df = fix_contracts_finder_flat_CSV(df)
                source_data.append(fixed_df)
            except pd.errors.EmptyDataError:
                pass

    source_df = pd.concat(source_data, ignore_index=True)
    source_df['publishedDate'] = pd.to_datetime(source_df['publishedDate'])

    # Filter for publisher names
    if publisher_names:
        logger.info("Filtering for named publishers")
        named_publishers = source_df['publisher/name'].isin(publisher_names)
        source_df = source_df[named_publishers]
        # source_df.to_csv()

    if not start_date:
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


def create_output_files(name, df, parent_directory, load_data):
    """
    Create a set of JSON format release package files from the DataFrame
    supplied for the releases where the type is tender or award. Load the data
    into the database if the load_data param is True.

    :param name: Name of the directory to create
    :param df: DataFrame containing the data
    :param parent_directory: Path to the parent directory to create the files
    :param load_data: Boolean indicating that the data should be loaded
    """
    release_types = ['tender', 'award']
    for release_type in release_types:
        logger.info("Creating output files for %s %s", name, release_type)

        release_name = name + "-" + release_type
        output_dir = join(parent_directory, release_name)
        os.makedirs(output_dir)
        json_file_path = join(output_dir, release_name + ".json")

        # Filter the DataFrame
        df_release_type = df[df['releases/0/tag'] == release_type]
        if df_release_type.shape[0] > 0:
            csv_file_name = release_name + ".csv"
            csv_file_path = join(output_dir, csv_file_name)

            last_published_date = df_release_type['publishedDate'].max()

            # Write the DataFrame to a CSV
            df_release_type.to_csv(open(csv_file_path, "w"), index=False, header=True)

            # Create fake simple submission CSV
            period_dir_name = os.path.basename(parent_directory)
            simple_csv_file_path = join(SAMPLE_SUBMISSIONS_DIR, f"{release_name}_{period_dir_name}.csv")
            mapper = CSVMapper(release_type=release_type)
            ocds_1_1_release_df = mapper.convert_cf_to_1_1(df_release_type)
            simple_csv_df = mapper.output_simple_csv(ocds_1_1_release_df)
            simple_csv_df.to_csv(open(simple_csv_file_path, "w"), index=False, header=True)

            # Turn the CSV into releases package JSON
            schema = OCDS_RELEASE_SCHEMA
            unflatten(output_dir, output_name=json_file_path, input_format="csv", root_id="ocid", root_is_list=True, schema=schema)

            # Combine the packages from the file into one release package and
            # write it back to the file
            js = json.load(open(json_file_path))
            publisher = js[0]["publisher"]
            uri = js[0]["uri"]
            release_package = combine_release_packages(js, uri=uri, publisher=publisher, published_date=last_published_date, version='1.1')
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
        parser.add_argument("--publisher_submissions", action='store_true', help="Group data into publisher submissions")
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
            shutil.copy(file_path, SOURCE_DIR)
        elif start_date:
            daterange = pd.date_range(start_date, end_date)
            logger.info("Downloading Contracts Finder data from %s to %s", start_date, end_date)
            for date in daterange:
                try:
                    date_string = f"{date.year}/{date.month:02}/{date.day:02}"
                    url = f"https://www.contractsfinder.service.gov.uk/Harvester/Notices/Data/CSV/{date_string}"
                    urllib.request.urlretrieve(url, join(SOURCE_DIR, slugify(date_string) + ".csv"))
                    logger.info("Downloading URL: %s", url)
                except TypeError:
                    logger.exception("Error with URL: %s", url)
        else:
            self.print_help('manage.py', '<your command name>')
            sys.exit()

        process_contracts_finder_csv(publisher_names, start_date, end_date, options)
