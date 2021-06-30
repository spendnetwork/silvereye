import os
from collections import OrderedDict

import environ
from environ.compat import DJANGO_POSTGRES

from cove import settings

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

env = environ.Env(  # set default values and casting
    DB_NAME=(str, os.path.join(BASE_DIR, "db.sqlite3")),
    HOTJAR_ID=(str, ""),
    HOTJAR_SV=(str, ""),
    HOTJAR_DATE_INFO=(str, ""),
    ALLOWED_HOSTS = (list,["127.0.0.1", "localhost"])
)


PIWIK = settings.PIWIK
GOOGLE_ANALYTICS_ID = settings.GOOGLE_ANALYTICS_ID
HOTJAR = {
    "id": env("HOTJAR_ID"),
    "sv": env("HOTJAR_SV"),
    "date_info": env("HOTJAR_DATE_INFO"),
}

# We can't take MEDIA_ROOT and MEDIA_URL from cove settings,
# ... otherwise the files appear under the BASE_DIR that is the Cove library install.
# That could get messy. We want them to appear in our directory.
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"

DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
CACHE_VALIDATION_ERRORS = True

# Set variable to "TRUE" to enable
STORE_OCDS_IN_S3 = os.getenv('STORE_OCDS_IN_S3') == 'TRUE'
if STORE_OCDS_IN_S3:
    # AWS settings
    # DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    S3_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', 'spendnetwork-silvereye')
    AWS_LOCATION = os.getenv('AWS_LOCATION', 'media')
    AWS_DEFAULT_ACL = None

# Heroku doesn't have git support when deploying
DEALER_TYPE = 'null'

SECRET_KEY = settings.SECRET_KEY
DEBUG = settings.DEBUG
ALLOWED_HOSTS = settings.ALLOWED_HOSTS

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    "bootstrap4",
    "cove",
    "cove.input",
    "cove_ocds",

    'storages',

    'bluetail',
    'silvereye',
    'django_pgviews',
    'pipeline',
    'debug_toolbar',
    'mathfilters',
]


MIDDLEWARE = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # "dealer.contrib.django.Middleware",
    "cove.middleware.CoveConfigCurrentApp",
)


ROOT_URLCONF = "cove_project.urls"

TEMPLATES = settings.TEMPLATES
TEMPLATES[0]["DIRS"].append(os.path.join(BASE_DIR, "cove_project", "templates"))
TEMPLATES[0]["DIRS"].append(os.path.join(BASE_DIR, "bluetail", "templates"))
TEMPLATES[0]["DIRS"].append(os.path.join(BASE_DIR, "silvereye", "templates"))
TEMPLATES[0]["OPTIONS"]["context_processors"].append(
    "cove_project.context_processors.analytics"
)

WSGI_APPLICATION = "cove_project.wsgi.application"

# We can't take DATABASES from cove settings,
# ... otherwise the files appear under the BASE_DIR that is the Cove library install.
# That could get messy. We want them to appear in our directory.

DATABASES = {'default': env.db()}

# Automatically use psqlextra if postgres is detected.
USE_PSQL_EXTRA = DATABASES['default']['ENGINE'] == DJANGO_POSTGRES
if USE_PSQL_EXTRA:
    DATABASES['default']['ENGINE'] = 'psqlextra.backend'
    INSTALLED_APPS += ['psqlextra']

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = settings.LANGUAGE_CODE
TIME_ZONE = settings.TIME_ZONE
USE_I18N = settings.USE_I18N
USE_L10N = settings.USE_L10N
USE_TZ = settings.USE_TZ

LANGUAGES = settings.LANGUAGES

LOCALE_PATHS = (os.path.join(BASE_DIR, "cove_ocds", "locale"),)

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

# We can't take STATIC_URL and STATIC_ROOT from cove settings,
# ... otherwise the files appear under the BASE_DIR that is the Cove library install.
# and that doesn't work with our standard Apache setup.
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")

# Misc
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s '
                      '%(process)d %(thread)d %(message)s'
        },
        'standard': {
            'format': '%(levelname)s %(asctime)s %(module)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        }
    },
    'loggers': {
        'django.db.backends': {
            'level': 'ERROR',
            'handlers': ['console'],
            'propagate': False,
        },
        '': {
            'level': 'WARNING',
            'handlers': ['console'],
        },
    },
}
LOGGING["handlers"]["null"] = {
    "class": "logging.NullHandler",
}
LOGGING["loggers"]["django.security.DisallowedHost"] = {
    "handlers": ["null"],
    "propagate": False,
}

# OCDS Config

COVE_CONFIG = {
    "app_name": "silvereye",
    # "app_base_template": "cove_ocds/base.html",
    "app_base_template": "bluetail_and_silvereye_shared/base.html",
    "app_verbose_name": "Open Contracting Data Review Tool",
    "app_strapline": "Review your OCDS data.",
    "schema_name": {
        "release": "release-package-schema.json",
        "record": "record-package-schema.json",
    },
    "schema_item_name": "release-schema.json",
    "schema_host": None,
    "schema_version_choices": OrderedDict(
        (  # {version: (display, url)}
            ("1.0", ("1.0", "https://standard.open-contracting.org/schema/1__0__3/")),
            ("1.1", ("1.1", "https://standard.open-contracting.org/schema/1__1__4/")),
        )
    ),
    "schema_codelists": OrderedDict(
        (  # {version: codelist_dir}
            (
                "1.1",
                "https://raw.githubusercontent.com/open-contracting/standard/1.1/standard/schema/codelists/",
            ),
        )
    ),
    "root_list_path": "releases",
    "root_id": "ocid",
    "convert_titles": False,
    "input_template": "silvereye/input.html",
    "input_methods": [
        "upload",
        "url",
        # "text"
    ],
    "support_email": "data@open-contracting.org",
}

# Set default schema version to the latest version
COVE_CONFIG["schema_version"] = list(COVE_CONFIG["schema_version_choices"].keys())[-1]

# https://github.com/OpenDataServices/cove/issues/1098
FILE_UPLOAD_PERMISSIONS = 0o644

URL_PREFIX = r"review/"

# Because of how the standard site proxies traffic, we want to use this
USE_X_FORWARDED_HOST = True



# Bluetail settings

BLUETAIL_APP_DIR = os.path.join(BASE_DIR, "bluetail")
COMPANY_ID_SCHEME = os.getenv("COMPANY_ID_SCHEME", 'GB-COH')

# pipeline
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

    'CSS_COMPRESSOR': 'silvereye.helpers.CssCompressor',
    'DISABLE_WRAPPER': True,
    'COMPILERS': (
        'pipeline.compilers.sass.SASSCompiler',
    ),
    'SHOW_ERRORS_INLINE': False,
    # Use the libsass commandline tool (that's bundled with libsass) as our
    # sass compiler, so there's no need to install anything else.
    'SASS_BINARY': SASS_BINARY,
}

# Needed for DEBUG TOOLBAR
INTERNAL_IPS = [
    "127.0.0.1",
]

# Silvereye
CSV_MAPPINGS_PATH = os.path.join(BASE_DIR, "silvereye", "data", "csv_mappings", "release_mappings.csv")