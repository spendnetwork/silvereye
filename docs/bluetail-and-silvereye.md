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
