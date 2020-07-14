import os
from collections import OrderedDict

import environ
from cove import settings

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

env = environ.Env(  # set default values and casting
    DB_NAME=(str, os.path.join(BASE_DIR, "db.sqlite3")),
    HOTJAR_ID=(str, ""),
    HOTJAR_SV=(str, ""),
    HOTJAR_DATE_INFO=(str, ""),
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
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "bootstrap3",
    "cove",
    "cove.input",
    "cove_ocds",

    'storages',
]


MIDDLEWARE = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'whitenoise.middleware.WhiteNoiseMiddleware',
    "django.middleware.security.SecurityMiddleware",
    # "dealer.contrib.django.Middleware",
    "cove.middleware.CoveConfigCurrentApp",
)


ROOT_URLCONF = "cove_project.urls"

TEMPLATES = settings.TEMPLATES
TEMPLATES[0]["DIRS"] = [os.path.join(BASE_DIR, "cove_project", "templates")]
TEMPLATES[0]["OPTIONS"]["context_processors"].append(
    "cove_project.context_processors.analytics"
)

WSGI_APPLICATION = "cove_project.wsgi.application"

# We can't take DATABASES from cove settings,
# ... otherwise the files appear under the BASE_DIR that is the Cove library install.
# That could get messy. We want them to appear in our directory.
DATABASES = {
    'default': env.db()
}

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

LOGGING = settings.LOGGING
LOGGING["handlers"]["null"] = {
    "class": "logging.NullHandler",
}
LOGGING["loggers"]["django.security.DisallowedHost"] = {
    "handlers": ["null"],
    "propagate": False,
}

# OCDS Config

COVE_CONFIG = {
    "app_name": "cove_ocds",
    "app_base_template": "cove_ocds/base.html",
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
    "input_template": "cove_ocds/input.html",
    "input_methods": ["upload", "url", "text"],
    "support_email": "data@open-contracting.org",
}

# Set default schema version to the latest version
COVE_CONFIG["schema_version"] = list(COVE_CONFIG["schema_version_choices"].keys())[-1]

# https://github.com/OpenDataServices/cove/issues/1098
FILE_UPLOAD_PERMISSIONS = 0o644

URL_PREFIX = r"review/"

# Because of how the standard site proxies traffic, we want to use this
USE_X_FORWARDED_HOST = True
