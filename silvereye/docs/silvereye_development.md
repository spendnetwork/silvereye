# Silvereye development docs

## Local development

### Debug mode

To enable debug mode and the Django Debug Toolbar add these to your `.env`:

    DEBUG=True
    DEBUG_TOOLBAR=True
    
### Updating requirements

Silvereye uses [pip-tools](https://github.com/jazzband/pip-tools) for managing python requirements.
Make any changes to either of
 
    requirements.in
    requirements_dev.in
    
Then compile the changes to `requirements.txt`

    pip-compile
    
If you need to compile changes to `requirements_dev.txt`, then run

    pip-compile requirements_dev.in
 

### Testing

Run pytest

    pytest silvereye
    

## Merging silvereye/bluetail to cove-ocds

Notes about the merging of silvereye and bluetail code to the cove-ocds fork early in development are kept for reference 
[here](bluetail-and-silvereye.md)