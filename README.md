
The DRT is a web application that allows you to review Open Contracting data, validate it against the Open Contracting Data Standard, and review it for errors or places for improvement. You can also use it to covert data between JSON and Excel spreadsheet formats.

It runs at `standard.open-contracting.org/review/ <https://standard.open-contracting.org/review/>`_.


## Modified Review Tool

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


## Steps taken when merging Bluetail/Silvereye into cove-ocds

- copy bluetail/silvereye app directories
- update INSTALLED_APPS:


        'bluetail',
        'silvereye',
        'django_pgviews',
        'pipeline',
    
- updated settings.py 
    - Need BLUETAIL_APP_DIR for management commands
    
        ```
        BLUETAIL_APP_DIR = os.path.join(BASE_DIR, "bluetail")
        ```
      
    - Add bluetail/silvereye template dirs
    
        ```
        TEMPLATES[0]["DIRS"] = [os.path.join(BASE_DIR, "bluetail", "templates")]
        TEMPLATES[0]["DIRS"] = [os.path.join(BASE_DIR, "silvereye", "templates")]
        ```
      
    - Django pipeline and static settings
    
        ```
        if DEBUG:
            IS_LIVE = False
            STATICFILES_STORAGE = 'pipeline.storage.NonPackagingPipelineStorage'
        else:
            IS_LIVE = True
            STATICFILES_STORAGE = 'pipeline.storage.PipelineStorage'

        STATICFILES_FINDERS = (
            'django.contrib.staticfiles.finders.FileSystemFinder',
            'django.contrib.staticfiles.finders.AppDirectoriesFinder',
            'pipeline.finders.PipelineFinder',
        )

        VENDOR_DIR = os.path.join(BLUETAIL_APP_DIR, "vendor")
        # Define some custom locations at which the staticfiles app can find our
        # files, which it will collect in the directory defined by `STATIC_ROOT`.
        # django-pipeline will then compile them from there (if required).
        STATICFILES_DIRS = (
            (
                "bootstrap",
                os.path.join(VENDOR_DIR, "bootstrap", "scss"),
            ),
            (
                "html5shiv",
                os.path.join(VENDOR_DIR, "html5shiv"),
            ),
            (
                "jquery",
                os.path.join(VENDOR_DIR, "jquery"),
            ),
            (
                "bootstrap",
                os.path.join(VENDOR_DIR, "bootstrap", "dist", "js"),
            )
        )

        SASS_BINARY = os.getenv('SASS_BINARY', 'sassc')

        PIPELINE = {
            'STYLESHEETS': {
                'main': {
                    'source_filenames': (
                        'sass/main.scss',
                    ),
                    'output_filename': 'css/main.css',
                },
            },

            'CSS_COMPRESSOR': 'django_pipeline_csscompressor.CssCompressor',
            'DISABLE_WRAPPER': True,
            'COMPILERS': (
                'pipeline.compilers.sass.SASSCompiler',
            ),
            'SHOW_ERRORS_INLINE': False,
            # Use the libsass commandline tool (that's bundled with libsass) as our
            # sass compiler, so there's no need to install anything else.
            'SASS_BINARY': SASS_BINARY,
        }
        ```
- Add url paths to project urls.py
    
    ```
    path(r'', include('bluetail.urls')),
    path('publisher-hub/', include('silvereye.urls')),
    ```
 
- Run commands for migrations and data 

    ```   
    python manage.py migrate
    python manage.py sync_pgviews --force
    python manage.py insert_prototype_data
    python manage.py insert_contracts_finder_data --anonymise
    python manage.py generate_fake_popolo > fake_popolo.json
    python manage.py load_identifiers_from_popolo fake_popolo.json person_id_matches_cabinet_minister
    rm fake_popolo.json
    python manage.py scan_contracts
    ```

- Update .gitignore with the /static/ dir

    ```
    /static/
    ```