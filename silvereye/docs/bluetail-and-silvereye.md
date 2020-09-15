# Usage of bluetail in Silvereye

The bluetail project is a prototype Django app that links OCDS and BODS data to help highlight suspicious 
behaviour in government procurement.

More documentation is here https://github.com/mysociety/bluetail

Silvere includes the bluetail app to make use of Django models for storing and viewing OCDS data in Postgres.

In particular it uses these objects:

- `bluetail/migrations`
    - bluetail migrations are needed to generate the OCDS tables 

- `bluetail/helpers.py:UpsertDataHelpers.upsert_ocds_data()`
    - method used to insert OCDS JSON data into the database

- `bluetail.models.ocds_models.py`
    - OCDSPackageData model used in Silvereye views 
    - OCDSReleaseView model used in Silvereye views

- `bluetail/templates/bluetail_and_silvereye_shared/base.html`
   - used for silvereye templates in place of the cove-ocds base by updating the setting in `cove_project/settings.py`
            
            COVE_CONFIG = {
                "app_name": "silvereye",
                # "app_base_template": "cove_ocds/base.html",
                "app_base_template": "bluetail_and_silvereye_shared/base.html",   

The rest of bluetail is superfluous to Silvereye and can be remove if desired.


## Steps taken when merging Bluetail and Silvereye into cove-ocds

This is here for reference of the changes made to the original fork to enable bluetail/silvereye to work.

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
