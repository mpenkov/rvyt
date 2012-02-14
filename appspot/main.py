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
import urllib2
import urlparse
import time
import wsgiref.handlers
import simplejson

import reddit

from google.appengine.api import channel
from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import webapp

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

from oauth2client.appengine import oauth2decorator_from_clientsecrets
from oauth2client.client import AccessTokenRefreshError

import gdata.youtube
import gdata.youtube.service
import gdata.service
from gdata.auth import OAuthToken, OAuthInputParams

import logging

# CLIENT_SECRETS, name of a file containing the OAuth 2.0 information for this
# application, including client_id and client_secret, which are found
# on the API Access tab on the Google APIs
# Console <http://code.google.com/apis/console>
CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), 'client_secrets.json')

# Helpful message to display in the browser if the CLIENT_SECRETS file
# is missing.
MISSING_CLIENT_SECRETS_MESSAGE = """
<h1>Warning: Please configure OAuth 2.0</h1>
<p>
To make this sample run you will need to populate the client_secrets.json file
found at:
</p>
<p>
<code>%s</code>.
</p>
<p>with information found on the <a
href="https://code.google.com/apis/console">APIs Console</a>.
</p>
""" % CLIENT_SECRETS

#
# TODO: <shameless_copy_paste>
#

USER_AGENT = 'http://rvytpl.appspot.com'
YOUTUBE_DEVELOPER_KEY = 'AI39si4TTIXb-M4G0rhm4kG1eYowjK2tlHZlrxGS4vOegXEK0oS3LRrmx-PMbrMRVtfHqpJ6gG60qQ2U4w6X_DnqfmkuqtTDvA'

OAUTH_METHOD = gdata.oauth.OAuthSignatureMethod_HMAC_SHA1
GDATA_URL = 'http://gdata.youtube.com', 

http = httplib2.Http(memcache)
decorator = oauth2decorator_from_clientsecrets(
    CLIENT_SECRETS,
    'http://gdata.youtube.com',
    MISSING_CLIENT_SECRETS_MESSAGE)

"""Fetch and keep this many entries from the subreddit."""
REDDIT_ENTRY_LIMIT = 100

class RedditEntry(db.Model):
    """An entity to hold information about a single Reddit entry."""
    rank = db.IntegerProperty(required=True)
    title = db.StringProperty(required=True)
    url = db.StringProperty(required=True)
    permalink = db.StringProperty(required=True)
    score = db.IntegerProperty(required=True)
    timestamp = db.DateTimeProperty(required=True)

class MyOAuthToken(OAuthToken):
    """This is a an ugly hack to make the old 1.0 API work with OAuth2."""
    def __init__(self, *args):
        OAuthToken.__init__(self, *args)

    def GetAuthHeader(self, http_method, http_url, realm=''):
        #
        # http://code.google.com/apis/youtube/2.0/developers_guide_protocol_oauth2.html#OAuth2_Client_Libraries
        #
        return { 'Authorization' : 'Bearer %s' % self.key }

def credentials_to_oauth_token(credentials):
    """
    Create an OAuthToken that can be used with the GData 1.0 API from a
    Credentials object.
    """
    params = OAuthInputParams(
            OAUTH_METHOD,
            credentials.client_id,
            credentials.client_secret)
    token = MyOAuthToken(
            credentials.access_token, 
            credentials.client_secret, 
            GDATA_URL,
            params)    
    return token

def youtube_login(token):
    """Login to YouTube using an OAuth2 token."""
    yt_service = gdata.youtube.service.YouTubeService()
    yt_service.SetOAuthToken(token)
    yt_service.developer_key = YOUTUBE_DEVELOPER_KEY
    yt_service.source = USER_AGENT
    return yt_service

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

def get_video_id_from_url(url):
    """
    If the specified URL is a YouTube video, returns the video ID.
    Otherwise, returns None.
    """
    p = urlparse.urlparse(url)
    compo = p.path.split('/')
    if p.netloc in [ 'www.youtu.be', 'youtu.be' ]:
        return compo[1]
    elif p.netloc in [ 'www.youtube.com', 'youtube.com' ]:
        args = p.query.split(';')
        video_id = None
        try:
            for key,val in map(lambda f: f.split('='), args):
                if key == 'v':
                    return val[:11]
        except ValueError:
            pass
        return None
    else:
        return None

def get_playlist_id_from_title(youtube_api, title):
    """
    Returns the ID of the playlist with the specified title if it exists, or
    None.
    """
    playlist_feed = youtube_api.GetYouTubePlaylistFeed()
    for pl in playlist_feed.entry:
        if pl.title.text == title:
            return pl.id.text
    return None

#
# TODO: </shameless_copy_paste>
#

class MainPage(webapp.RequestHandler):
    """
    The index page.  This is what people see when they first come to 
    the site.
    """
    @decorator.oauth_aware
    def get(self):
        has_credentials = False
        if decorator.has_credentials():
            if decorator.credentials.access_token_expired:
                #
                # FIXME: this doesn't seem to work.
                #
                decorator.credentials.authorize(http)
            #
            # checking has_credentials() isn't enough for YouTube.
            # we need to make sure that an API call actually works.
            #
            token = credentials_to_oauth_token(decorator.credentials)
            yt_service = youtube_login(token)
            try:
                #
                # This is just a call to see if the YouTube Service is working 
                # correctly.  If this fails, then our token is bad.
                #
                playlist_feed = yt_service.GetYouTubePlaylistFeed()
                has_credentials = True
            except gdata.service.RequestError, re:
                logging.error('gdata.service.RequestError: ' + str(re))

        query = RedditEntry.all()
        for entry in query.fetch(1):
            last_update = entry.timestamp
        variables = {
                'url': decorator.authorize_url(),
                'has_credentials': has_credentials,
                'last_update' : last_update
            }
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, variables))

class Make(webapp.RequestHandler):
    @decorator.oauth_required
    def post(self):
        if decorator.credentials.access_token_expired:
            self.redirect('/')
            return

        title = self.request.get('title')
        description = self.request.get('description')
        limit = self.request.get('limit')

        channel_id = str(random.randint(1,10000))+str(datetime.datetime.now())
        channel.send_message(
                channel_id, simplejson.dumps({'status': 'initialized'} ))

        token = credentials_to_oauth_token(decorator.credentials)
        try:
            youtube_api = youtube_login(token)
        except gdata.service.Error, e:
            #
            # TODO
            #
            assert False

        playlist_id = get_playlist_id_from_title(youtube_api, title)
        if playlist_id:
            #
            # Dammit YouTube API, why do you have to be so inconsistent?
            # playlist.id.text works for DeletePlaylist, doesn't work for
            # AddPlaylistVideoEntryToPlaylist.
            # Passing a URI wroks for APVETP but not for DeletePlaylist.
            # FFS...
            #
            response = youtube_api.DeletePlaylist(playlist_id)
            if not response:
                #
                # TODO
                # 
                assert False

        new_playlistentry = youtube_api.AddPlaylist(title, description)
        if isinstance(new_playlistentry, gdata.youtube.YouTubePlaylistEntry):
            playlist_id = new_playlistentry.id.text.split('/')[-1]
        else:
            #
            # TODO
            #
            assert False

        plist_uri = 'http://gdata.youtube.com/feeds/api/playlists/' + playlist_id
        plist_url = 'http://www.youtube.com/playlist?list=' + playlist_id

        template_values = { 
                'token': channel.create_channel(channel_id),
                'plist_uri' : plist_uri, 
                'plist_url' : plist_url,
                'channel_id' : channel_id,
                'limit' : limit }
        path = os.path.join(os.path.dirname(__file__), 'make.html')
        self.response.out.write(template.render(path, template_values))

class Opened(webapp.RequestHandler):
    """
    This page gets posted to when a channel has been opened.  This means its
    OK to start a worker to communicate with that channel.  This class puts
    the workers on the task queue.
    """
    @decorator.oauth_required
    def post(self):
        token = credentials_to_oauth_token(decorator.credentials)
        limit = int(self.request.get('limit'))

        query = RedditEntry.all()
        query.order('rank')
        entries = query.fetch(limit)
        for i,v in enumerate(entries):
            #
            # FIXME: calls inside this loop can fail with "too many recent
            # calls".  Need to handle that exception as otherwise it will force
            # a restart of the task, which is not good.
            #
            video_id = get_video_id_from_url(v.url)
            params = { 
                    'plist_uri' : self.request.get('plist_uri'),
                    'channel_id' : self.request.get('channel_id'),
                    'limit': str(limit),
                    'video_id' : video_id,
                    'title' : v.title,
                    'permalink' : v.permalink,
                    'token' : str(pickle.dumps(token))
                }
            taskqueue.add(url='/worker', params=params)
        
class Worker(webapp.RequestHandler):
    """
    This is a task that gets put on the task queue by the Opened class.
    It performs the addition of a single video to some playlist.
    It communicates with the client-side JavaScript via the Channel API.
    """
    def post(self):
        channel_id = self.request.get('channel_id')
        plist_uri = self.request.get('plist_uri')
        video_id = self.request.get('video_id')
        title = self.request.get('title')
        permalink = self.request.get('permalink')

        #
        # It appears that it's impossible to use the OAuth decorators here, so
        # we pass the token through the POST parameters instead.  Unpickling
        # from Unicode seems to fail, so convert to regular string.
        #
        token_str = str(self.request.get('token'))
        token = pickle.loads(token_str)

        #
        # Honor the YouTube API limits.
        #
        time.sleep(1)

        try:
            youtube_api = youtube_login(token)
            plve = youtube_api.AddPlaylistVideoEntryToPlaylist(
                plist_uri, video_id, title, permalink)
            if not isinstance(plve, gdata.youtube.YouTubePlaylistVideoEntry):
                raise gdata.service.Error, 'bad instance'
        except gdata.service.Error, err:
            logging.error('gdata.service.Error' + str(err))
        channel.send_message(channel_id, 'done')

class Updater(webapp.RequestHandler):
    """Pull REDDIT_ENTRY_LIMIT entries from /r/videos into the data store."""
    def get(self):
        query = RedditEntry.all()
        for entry in query.fetch(REDDIT_ENTRY_LIMIT):
            entry.delete()

        reddit_api = reddit.Reddit(user_agent=USER_AGENT)
        subreddit = reddit_api.get_subreddit('videos').get_top(
                limit=REDDIT_ENTRY_LIMIT)
        rank = 1
        while True:
            try:                
                entry = subreddit.next()
                timestamp = datetime.datetime.now()
                store = RedditEntry(
                        rank=rank,
                        title=entry.title.replace('\n', ' '),
                        url=entry.url,
                        permalink=entry.permalink,
                        score=entry.score,
                        timestamp=timestamp)
                store.put()
                #
                # This sleep is here to prevent the below HTTP error.
                # It seems to help.
                #
                time.sleep(0.25)
                rank += 1
            except urllib2.HTTPError, err:
                logging.error(err)
                break
            except ValueError, err:
                logging.error(err)
                break
            except StopIteration:
                logging.info('caught StopIteration')
                break

        logging.info('read %d entries' % (rank-1))

        query = RedditEntry.all()
        query.order('rank')
        entries = query.fetch(REDDIT_ENTRY_LIMIT)

        path = os.path.join(os.path.dirname(__file__), 'update.html')
        template_values = { 'entries' : entries }
        self.response.out.write(template.render(path, template_values))

application = webapp.WSGIApplication([
  ('/', MainPage),
  ('/make', Make),
  ('/worker', Worker),
  ('/update', Updater),
  ('/opened', Opened)
], debug=True)


def main():
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
