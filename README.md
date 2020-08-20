
- [Silvereye](#silvereye)
  * [Installation](#installation)
    + [Running Silvereye locally (with Vagrant)](#running-silvereye-locally-with-vagrant)
    + [Running Silvereye locally (without Vagrant)](#running-silvereye-locally-without-vagrant)
    + [Deployment to Heroku](#deployment-to-heroku)
    + [Data loading](#data-loading)
        + [Loading data from Contracts Finder](#loading-data-from-contracts-finder)
        + [Updating publisher metadata](#updating-publisher-metadata)
        + [Preparing publisher metrics](#preparing-publisher-metrics)
    + [Admin](#admin)
  * [Data storage](#data-storage)
    + [S3 storage](#s3-storage)

# Silvereye

Silvereye is a modified fork of the Open Contracting repository `cove-ocds` (OCDS Data Review Tool)

The DRT is a web application that allows you to review Open Contracting data, validate it against the Open Contracting Data Standard, and review it for errors or places for improvement. You can also use it to covert data between JSON and Excel spreadsheet formats.

The original tool runs at https://standard.open-contracting.org/review/

Documentation for the original tool is at https://ocds-data-review-tool.readthedocs.io/en/latest/

The Silvereye fork runs at https://ocds-silvereye.herokuapp.com

WIP Documentation for the fork is in the README.me https://github.com/spendnetwork/cove-ocds/blob/master/README.md

# Installation

## Running Silvereye locally (with Vagrant)

Clone the repository

```
git clone git@github.com:spendnetwork/silvereye.git
cd silvereye
```

A Vagrantfile is included for local development. Assuming you have [Vagrant](https://www.vagrantup.com/) installed, you can create a Vagrant VM with:

```
vagrant up
```

Then SSH into the VM, and run the server script:

```
vagrant ssh
script/server
```

The site will be visible at <http://localhost:8000>.

## Running Silvereye locally (without Vagrant)

See the original docs for local setup

https://ocds-data-review-tool.readthedocs.io/en/latest/#running-it-locally

There is an extra step needed to create the Postgres views after migrating

    script/migrate

If you need to reset your local DB during development (eg. after pulling updates to the migrations) run

    script/setup

# Deployment to Heroku

Set up database

    heroku run "script/setup" --app ocds-silvereye

Insert Contracts Finder data using defaults

    heroku run "script/insert_cf_data" --app ocds-silvereye

Manually update data from Contracts Finder with args

    heroku run "python manage.py get_cf_data --start_date 2020-06-01 --load_data" --app ocds-silvereye
    heroku run "python manage.py update_publisher_data" --app ocds-silvereye

# Data Loading

 To insert the sample data set run

    script/insert_cf_data

 ## Loading data from Contracts Finder

 There is a management command to insert data from the Contracts Finder API.
 https://www.contractsfinder.service.gov.uk/apidocumentation/Notices/1/GET-Harvester-Notices-Data-CSV

 This can point to a local file or provide arguments to retrieve files from the API directly in a date range

 Insert local sample file as weekly publisher submissions

    python manage.py get_cf_data --file_path silvereye/data/cf_daily_csv/export-2020-08-05.csv --load_data --publisher_submissions

Download Contracts Finder releases in a date range and insert as weekly publisher submissions

    python manage.py get_cf_data --start_date 2020-07-01 --end_date 2020-09-01 --load_data --publisher_submissions

## Updating publisher metadata

This command updates the contact details from the latest submitted file for each publisher

    python manage.py update_publisher_data

## Preparing publisher metrics

This management command will prepare metric data for the Silvereye Publisher page

    python manage.py update_publisher_metrics

## Admin

The admin interfaces are available at

http://localhost:8000/review/admin/

## Data storage

### S3 storage

The original cove-ocds has been modified to sync the SuppliedData files to S3.

To store the supplied data files in an S3 bucket add the following environment variables:

    STORE_OCDS_IN_S3=TRUE
    AWS_ACCESS_KEY_ID=""
    AWS_SECRET_ACCESS_KEY=""
    AWS_STORAGE_BUCKET_NAME=""

See https://github.com/spendnetwork/cove-ocds/blob/master/docs/s3-storage.md for more details
