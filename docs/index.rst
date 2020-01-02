OCDS Data Review Tool: Developer Documentation
==============================================

The DRT is a web application that allows you to review Open Contracting data, validate it against the Open Contracting Data Standard, and review it for errors or places for improvement. You can also use it to covert data between JSON and Excel spreadsheet formats.

It runs at `standard.open-contracting.org/review/ <https://standard.open-contracting.org/review/>`_.

This documentation is for people who wish to contribute to or modify the DRT.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Running it locally
------------------

* Clone the repository
* Change into the cloned repository
* Create a virtual environment (note this application uses python3)
* Activate the virtual environment
* Install dependencies
* Set up the database (sqlite3)
* Compile the translations
* Run the development server

.. code:: bash

    git clone https://github.com/open-contracting/cove-ocds.git
    cd cove-ocds
    virtualenv .ve --python=/usr/bin/python3
    source .ve/bin/activate
    pip install -r requirements_dev.txt
    python manage.py migrate
    python manage.py compilemessages
    python manage.py runserver 0.0.0.0:8000


Commandline interface
---------------------

You can pass a JSON file for review to the DRT at the commandline after installing it in a virtual environment.

.. code:: bash

    $ python manage.py ocds_cli [-h]
                                [--version] [-v {0,1,2,3}]
                                [--settings SETTINGS]
                                [--pythonpath PYTHONPATH]
                                [--traceback]
                                [--no-color]
                                [--schema-version SCHEMA_VERSION]
                                [--convert]
                                [--output-dir OUTPUT_DIR]
                                [--delete]
                                [--exclude-file]
                                file


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
