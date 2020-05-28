How to edit the stylesheet
==========================

First: Run the setup from :ref:`run_locally`.

Then:

.. code-block:: bash

    source .ve/bin/activate
    cd cove_ocds/sass

Edit a file:

* ``_bootstrap-variables-ocds.sass`` to change variables used by bootstrap (e.g. colors)
* ``_custom-ocds.sass`` to add extra CSS blocks.

Then, run the build command to generate the CSS files:

.. code-block:: bash

    ./build_ocds.sh

Finally, check the changes with runserver, as per usual.
