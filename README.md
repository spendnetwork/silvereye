
The DRT is a web application that allows you to review Open Contracting data, validate it against the Open Contracting Data Standard, and review it for errors or places for improvement. You can also use it to covert data between JSON and Excel spreadsheet formats.

It runs at `standard.open-contracting.org/review/ <https://standard.open-contracting.org/review/>`_.


## S3 storage

The original cove-ocds has been modified to sync the SuppliedData files to S3.

To store the supplied data files in an S3 bucket add the following environment variables:

    STORE_OCDS_IN_S3=TRUE
    AWS_ACCESS_KEY_ID=""
    AWS_SECRET_ACCESS_KEY=""
    AWS_STORAGE_BUCKET_NAME=""

### Background

Early attempts were made to update the Django DEFAULT_FILE_STORAGE to use S3 backend in `django-storages`  (https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html)
, but some of the functions in the dependent libraries
	`libcove`,
	`libcoveweb`,
	`libcoveocds`
	and `flattentool`,
require accessing files on local storage using a file path generated from the MEDIA_ROOT
which caused errors when the S3 backend was used.

### Current Implementation

A workaround was found to simply sync the local storage to/from S3 in the view `explore_data_context` from `libcoveweb` that loads the JSON for review

This was done by replacing the original view from `libcoveweb`

    cove.views.explore_data_context

with a modified one in 

    cove_ocds.views.explore_data_context

and updating the URL accordingly
    
    url(r"^data/(.+)$", cove_ocds.views.explore_ocds, name="explore")

The instance of the SuppliedData being read from, is modified so the FileField that stores the data, `original_file`,
 has its `storage` property temporarily changed to the S3 backend. 
 
        supplied_data_instance.original_file.storage = get_storage_class(settings.S3_FILE_STORAGE)()
     
Then the file is saved and the storage property is reset back to default

        supplied_data_instance.original_file.storage = get_storage_class(settings.DEFAULT_FILE_STORAGE)()

The S3 backend is stored in the settings variable:

    S3_FILE_STORAGE

See the code for more details `cove_ocds/views.py::78`

