"""Grab missing entries."""
import os
import os.path as P
import urllib
import urllib2
import time

from top_20 import COMMENTS_URL, COMMENTS_JSON, HEADERS, VALUES

#
# The proper way to get HTTP responses:
#
# http://docs.python.org/howto/urllib2.html
#

for f in os.listdir('data/missing'):
    comment_file = P.join('data', f)
    if not P.isfile(comment_file):
        while True:
            url = COMMENTS_URL % P.splitext(f)[0]
            print url

            data = urllib.urlencode(VALUES)
            req = urllib2.Request(url, data, HEADERS)

            response = urllib2.urlopen(req)
            comments_json = response.read()
            if (comments_json.startswith('{"error": 429}')):
                #
                # We're being rate-limited.  Wait a little bit of time before 
                # trying again.
                #
                print '429, sleeping'
                time.sleep(10)
                continue
            fout = open(comment_file, 'w')
            fout.write(comments_json)
            fout.close()
            break
