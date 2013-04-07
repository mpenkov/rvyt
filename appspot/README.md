Google App Engine Application
=============================

Prerequisites
-------------

- Google App Engine Python SDK: https://developers.google.com/appengine/downloads (save anywhere convenient)
- Google Gdata Python Client: https://code.google.com/p/gdata-python-client/ (save in ./atom and ./gdata)
- Simplejson: https://pypi.python.org/pypi/simplejson/ (save in ./simplejson)

Running Locally
---------------

Start the app server:

    misha@misha-diginnos:~/src/google_appengine$ python dev_appserver.py ~/git/rvyt/appspot/

Navigate to http://localhost:8000

Updating the Remote Application
-------------------------------

    misha@misha-diginnos:~/src/google_appengine$ ./appcfg.py update ~/git/rvyt/appspot/ --oauth2
