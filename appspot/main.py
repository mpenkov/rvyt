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
import simplejson
from xml.dom.minidom import parseString

from google.appengine.api import channel
from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import webapp

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

from oauth2client.client import AccessTokenRefreshError

import gdata.youtube
import gdata.youtube.service
import gdata.service
from gdata.auth import OAuthToken, OAuthInputParams

import logging

from collections import defaultdict

from common import CLIENT_SECRETS, USER_AGENT, YOUTUBE_DEVELOPER_KEY
from common import youtube_login, credentials_to_oauth_token
from admin import REDDIT_ENTRY_LIMIT, RedditEntry


PLAYLIST_URI = 'http://gdata.youtube.com/feeds/api/playlists/'
PLAYLIST_URL = 'http://www.youtube.com/playlist?list='

import common
decorator = common.create_decorator()

http = httplib2.Http(memcache)
DATETIME_FORMAT = '%H:%M %d/%m/%Y GMT'

from admin import vid_from_url, YouTubeEntry
#
# http://stackoverflow.com/questions/753052/strip-html-from-strings-in-python
#
from HTMLParser import HTMLParser

class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

def plist_id_from_title(youtube_api, title):
    """
    Returns the ID of the playlist with the specified title if it exists, or
    None.
    """
    playlist_feed = youtube_api.GetYouTubePlaylistFeed()
    for pl in playlist_feed.entry:
        if pl.title.text == title:
            return pl.id.text
    return None

SHORT_TITLE_LEN = 30

def scrub_string(s):
    s = s.replace('"', '&quot')
    s = s.replace("'", "&apos;")
    return s

class DummyEntry:
    pass

def get_current_entries():
    query = YouTubeEntry.all()
    entries = [ x for x in query ]
    youtube_entries = { }
    for e in entries:
        youtube_entries[e.video_id] = { 
                'category' : e.category, 'duration' : e.duration }

    query = RedditEntry.all()
    query.order('rank')
    entries = query.fetch(limit=REDDIT_ENTRY_LIMIT)

    if not entries:
        #
        # Generate some dummy data
        #
        for i in range(25):
            e = DummyEntry()
            e.permalink = 'http://foo.bar'
            e.url = 'http://youtube.com/watch?v=%11d' % i
            e.score = 1000
            e.title = 'dummy entry #%d' % i
            e.rank = i
            e.timestamp = datetime.datetime(2012,04,10,11,34)
            entries.append(e)

    last_update = entries[0].timestamp.strftime(DATETIME_FORMAT)
    all_entries = []
    current_index = 0
    for e in entries:
        vid = vid_from_url(e.url)
        elem = { 
                'permalink' : e.permalink, 
                'score' : e.score,
                'title' : scrub_string(e.title),
                'rank' : e.rank,
                'url' : e.url,
                'rank' : e.rank,
                'index' : current_index,
                'vid' : vid,
                'category' : '',
                'duration' : 0 }        
        if vid:
            current_index += 1
            try:
                elem['category'] = youtube_entries[vid]['category']
            except KeyError:
                pass
            try:
                elem['duration'] = youtube_entries[vid]['duration']
            except KeyError:
                pass

        if len(e.title) < SHORT_TITLE_LEN:
            elem['short'] = scrub_string(e.title)
        else:
            elem['short'] = scrub_string(e.title[:SHORT_TITLE_LEN] + '...')
        all_entries.append(elem)
    return all_entries, last_update

class EditPlaylistHandler(webapp.RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'edit_playlist.html')
        entries, last_update = get_current_entries()
        categories = self.request.get_all('cat')
        variables = { 
                'all_entries' : simplejson.dumps(entries),
                'first' : [ e['vid'] for e in entries if e['vid'] ][0],
                'categories' : simplejson.dumps(categories) }
        self.response.out.write(template.render(path, variables))

class EditPlaylistAuthHandler(webapp.RequestHandler):
    @decorator.oauth_required
    def get(self):
        if decorator.credentials.access_token_expired:
            self.redirect('/')
            return

        try:
            token = credentials_to_oauth_token(decorator.credentials)
            youtube_api = youtube_login(token)
            #
            # TODO: get videos viewed by this user.
            #
        except gdata.service.Error, err:
            logging.error('gdata.service.Error' + str(err))
            template_values = { 
                    'token' : '', 
                    'error' : parse_request_error(err) }

        path = os.path.join(os.path.dirname(__file__), 'edit_playlist.html')
        entries, last_update = get_current_entries()
        categories = self.request.get_all('cat')
        variables = { 
                'all_entries' : simplejson.dumps(entries),
                'first' : [ e['vid'] for e in entries if e['vid'] ][0],
                'categories' : simplejson.dumps(categories) }
        self.response.out.write(template.render(path, variables))

class WelcomeHandler(webapp.RequestHandler):
    def get(self):
        all_entries, last_update = get_current_entries()
        num = defaultdict(int)
        for e in all_entries:
            num[e['category']] += 1

        youtube_videos = [ e for e in all_entries if e['vid'] ]
        top_list = [ ]
        for i,entry in enumerate(youtube_videos[:15]):
            top_list.append(
"""<li>
[ %(score)s ] 
<a href="javascript:ytplayer.playVideoAt(%(index)s);">%(short)s</a></li>""" % entry)
        variables = { 'first' : youtube_videos[0]['vid'], 
                'playlist' : ','.join([ yt['vid'] for yt in youtube_videos ][1:]), 
                'last_update' : last_update, 
                'all_entries' : simplejson.dumps(all_entries),
                'top_list' : '\n'.join(top_list),
                #
                # FIXME: there has got to be a better way to do this...
                #
                'num_animals' : num['Animals'],
                'num_autos' : num['Autos'],
                'num_comedy' : num['Comedy'],
                'num_education' : num['Education'],
                'num_entertainment' : num['Entertainment'],
                'num_film' : num['Film'],
                'num_howto' : num['Howto'],
                'num_music' : num['Music'],
                'num_news' : num['News'],
                'num_people' : num['People'],
                'num_sports' : num['Sports'],
                'num_tech' : num['Tech'],
                'num_unknown' : num[''],
                }
        path = os.path.join(os.path.dirname(__file__), 'welcome.html')
        self.response.out.write(template.render(path, variables))

from save_playlist import StartPageHandler
from save_playlist import SavePlaylistHandler, SavePlaylistTask, ChannelOpenedHandler

application = webapp.WSGIApplication([
    ('/', WelcomeHandler),
    ('/start', StartPageHandler),
    ('/save_playlist', SavePlaylistHandler),
    ('/edit_playlist', EditPlaylistHandler),
    ('/edit_playlist_auth', EditPlaylistAuthHandler),
    ('/spl_task', SavePlaylistTask),
    ('/opened', ChannelOpenedHandler)
], debug=True)

def main():
  run_wsgi_app(application)

if __name__ == '__main__':
  main()
