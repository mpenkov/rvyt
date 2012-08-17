#
# http://stackoverflow.com/questions/5056719/using-httplib2-on-python-appengine
# 
import sys
sys.modules['ssl'] = None

import os
import cgi
import datetime
import httplib2
import logging
import pickle
import random
import urllib
import time
import wsgiref.handlers
from xml.dom.minidom import parseString

from google.appengine.api import channel
from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import webapp

from google.appengine.ext.webapp.util import run_wsgi_app

import gdata.youtube
import gdata.youtube.service
import gdata.service

import logging

from collections import defaultdict

from mako.template import Template
from mako.lookup import TemplateLookup
from mako import exceptions
lookup = TemplateLookup(directories=['.'], default_filters=['decode.utf8'], 
                    input_encoding='utf-8', output_encoding='utf-8')

from admin import REDDIT_ENTRY_LIMIT, RedditEntry, vid_from_url

SHORT_TITLE_LEN = 70
DATETIME_FORMAT = '%H:%M %d/%m/%Y GMT'

class WelcomeHandler(webapp.RequestHandler):
    def get(self):
        query = RedditEntry.all()
        query.order('rank')
        all_entries = query.fetch(limit=REDDIT_ENTRY_LIMIT)

        yt_entries = list()
        playlist = list()
        for e in all_entries:
            e.ytid = vid_from_url(e.url)
            if not e.ytid:
                continue
            e.title = e.title.replace('"', "'")
            e.short_title = e.title
            if len(e.short_title) >= SHORT_TITLE_LEN:
                e.short_title = e.short_title[:SHORT_TITLE_LEN] + "..."
            yt_entries.append(e)
            playlist.append(e.ytid)
        playlist = ",".join(playlist[1:])
        last_update = yt_entries[0].timestamp.strftime(DATETIME_FORMAT)
        template = lookup.get_template("welcome.html")
        variables = locals()
        del variables["self"]
        html = template.render(**variables)
        self.response.out.write(html)

application = webapp.WSGIApplication([ ('/', WelcomeHandler) ], debug=True)

def main():
  run_wsgi_app(application)

if __name__ == '__main__':
  main()
