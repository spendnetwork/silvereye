import json
import logging
import os
import shutil
import warnings
from datetime import datetime

import flattentool
from django.utils.translation import ugettext_lazy as _
from flattentool.json_input import BadlyFormedJSONError

from libcove.lib.exceptions import cove_spreadsheet_conversion_error
from silvereye import helpers

logger = logging.getLogger(__name__)


def filter_conversion_warnings(conversion_warnings):
    out = []
    for w in conversion_warnings:
        if w.category is flattentool.exceptions.DataErrorWarning:
            out.append(str(w.message))
        else:
            logger.warning(w)
    return out


@cove_spreadsheet_conversion_error
def convert_csv(
    upload_dir,
    upload_url,
    file_name,
    file_type,
    lib_cove_config,
    schema_url=None,
    replace=True,
    cache=True,
):
    context = {}
    output_file = "unflattened.json"
    converted_path = os.path.join(upload_dir, "unflattened.json")
    cell_source_map_path = os.path.join(upload_dir, "cell_source_map.json")
    heading_source_map_path = os.path.join(upload_dir, "heading_source_map.json")
    encoding = "utf-8-sig"

    if file_type == "csv":
        # flatten-tool expects a directory full of CSVs with file names
        # matching what xlsx titles would be.
        # If only one upload file is specified, we rename it and move into
        # a new directory, such that it fits this pattern.
        input_name = os.path.join(upload_dir, "csv_dir")
        os.makedirs(input_name, exist_ok=True)
        destination = os.path.join(
            input_name, lib_cove_config.config["root_list_path"] + ".csv"
        )
        shutil.copy(file_name, destination)
        try:
            with open(destination, encoding="utf-8-sig") as main_sheet_file:
                main_sheet_file.read()
        except UnicodeDecodeError:
            try:
                with open(destination, encoding="cp1252") as main_sheet_file:
                    main_sheet_file.read()
                encoding = "cp1252"
            except UnicodeDecodeError:
                encoding = "latin_1"

        # Convert Simple CSV to OCDS URIs
        df = helpers.CSVMapper().convert_simple_csv_to_ocds_csv(destination)

    # Prepare base_json
    base_json = {
        "version": "1.1",
        "publisher": {
            "name": "PUBLISHER_NAME",
            "scheme": "PUBLISHER_SCHEME",
            "uid": "PUBLISHER_ID",
        },
        "publishedDate": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        # "license": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/2/",
        # "publicationPolicy": "https://www.gov.uk/government/publications/open-contracting",
        "uri": "https://ocds-silvereye.herokuapp.com/"
    }
    base_json_path = os.path.join(upload_dir, "base.json")
    with open(base_json_path, "w") as writer:
        json.dump(base_json, writer, indent=2)

    flattentool_options = {
        "output_name": converted_path,
        "base_json": base_json_path,
        "input_format": file_type,
        "default_configuration": "RootListPath {}".format(
            lib_cove_config.config["root_list_path"]
        ),
        "encoding": encoding,
        "cell_source_map": cell_source_map_path,
        "heading_source_map": heading_source_map_path,
        # "metatab_schema": pkg_schema_url,
        # "metatab_name": metatab_name,
        # "metatab_vertical_orientation": True,
        "disable_local_refs": lib_cove_config.config["flatten_tool"][
            "disable_local_refs"
        ],
    }


    if lib_cove_config.config.get("hashcomments"):
        flattentool_options["default_configuration"] += ",hashcomments"

    flattentool_options.update(
        {
            "schema": schema_url,
            "convert_titles": True,
            "root_id": lib_cove_config.config["root_id"],
            "root_is_list": lib_cove_config.config.get("root_is_list", False),
            "id_name": lib_cove_config.config.get("id_name", None),
        }
    )

    conversion_warning_cache_path = os.path.join(
        upload_dir, "conversion_warning_messages.json"
    )
    if (
        not os.path.exists(converted_path)
        or not os.path.exists(cell_source_map_path)
        or replace
    ):
        with warnings.catch_warnings(record=True) as conversion_warnings:
            flattentool.unflatten(input_name, **flattentool_options)
            context["conversion_warning_messages"] = filter_conversion_warnings(
                conversion_warnings
            )

        if cache:
            with open(conversion_warning_cache_path, "w+") as fp:
                json.dump(context["conversion_warning_messages"], fp)

    elif os.path.exists(conversion_warning_cache_path):
        with open(conversion_warning_cache_path) as fp:
            context["conversion_warning_messages"] = json.load(fp)

    context["converted_file_size"] = os.path.getsize(converted_path)

    context.update(
        {
            "conversion": "unflatten",
            "converted_path": converted_path,
            "converted_url": "{}{}{}".format(
                upload_url, "" if upload_url.endswith("/") else "/", output_file
            ),
            "csv_encoding": encoding,
        }
    )
    return context

