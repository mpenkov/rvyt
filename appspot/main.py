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

from oauth2client.appengine import oauth2decorator_from_clientsecrets
from oauth2client.client import AccessTokenRefreshError

import gdata.youtube
import gdata.youtube.service
import gdata.service
from gdata.auth import OAuthToken, OAuthInputParams

import logging

from collections import defaultdict

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

from admin import USER_AGENT, REDDIT_ENTRY_LIMIT, RedditEntry
YOUTUBE_DEVELOPER_KEY = 'AI39si4TTIXb-M4G0rhm4kG1eYowjK2tlHZlrxGS4vOegXEK0oS3LRrmx-PMbrMRVtfHqpJ6gG60qQ2U4w6X_DnqfmkuqtTDvA'

OAUTH_METHOD = gdata.oauth.OAuthSignatureMethod_HMAC_SHA1
GDATA_URL = 'http://gdata.youtube.com', 

PLAYLIST_URI = 'http://gdata.youtube.com/feeds/api/playlists/'
PLAYLIST_URL = 'http://www.youtube.com/playlist?list='

http = httplib2.Http(memcache)
decorator = oauth2decorator_from_clientsecrets(
    CLIENT_SECRETS,
    'http://gdata.youtube.com',
    MISSING_CLIENT_SECRETS_MESSAGE)

DATETIME_FORMAT = '%H:%M %d/%m/%Y GMT'

from admin import vid_from_url, YouTubeEntry

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

def get_current_entries():
    query = YouTubeEntry.all()
    entries = [ x for x in query ]
    youtube_entries = { }
    for e in entries:
        youtube_entries[e.video_id] = { 'category' : e.category }

    query = RedditEntry.all()
    query.order('rank')
    entries = query.fetch(limit=REDDIT_ENTRY_LIMIT)

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
                'vid' : vid }        
        if vid:
            current_index += 1
            try:
                elem['category'] = youtube_entries[vid]['category']
            except KeyError:
                elem['category'] = ''
        else:
            elem['category'] = ''

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

class WelcomeHandler(webapp.RequestHandler):
    def get(self):
        all_entries, last_update = get_current_entries()
        num = defaultdict(int)
        for e in all_entries:
            num[e['category']] += 1

        youtube_videos = [ e for e in all_entries if e['vid'] ]
        top_list = [ ]
        for i,entry in enumerate(youtube_videos[:20]):
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

class MainPageHandler(webapp.RequestHandler):
    @decorator.oauth_aware
    def get(self):
        has_credentials = False
        if decorator.has_credentials():
            try:
                user = users.get_current_user()
                logging.info('current user: %s' % user.nickname())
                if decorator.credentials.access_token_expired:
                    #
                    # TODO: I'm not sure why I have to call a private method
                    # to do this, but it seems to do the trick.
                    #
                    decorator.credentials._refresh(http.request)
                #
                # checking has_credentials() isn't enough for YouTube.
                # we need to make sure that an API call actually works.
                #
                token = credentials_to_oauth_token(decorator.credentials)
                yt_service = youtube_login(token)

                #
                # This is to see if the YouTube Service is working correctly.
                # If this fails, then our token is bad.
                #
                playlist_feed = yt_service.GetYouTubePlaylistFeed()
                has_credentials = True
            except gdata.service.Error, err:
                logging.error('gdata.service.RequestError: ' + str(err))
            except AccessTokenRefreshError, atre:
                logging.error('AccessTokenRefreshError:' + str(atre))
        else:
            logging.info('current user: guest')

        entry = RedditEntry.all().get()
        variables = {
                'url': decorator.authorize_url(),
                'has_credentials': has_credentials
            }
        path = os.path.join(os.path.dirname(__file__), 'start.html')
        self.response.out.write(template.render(path, variables))

def parse_request_error(err):
    body = err[0]['body']
    if body.startswith("<?xml version='1.0' encoding='UTF-8'?>"):
        dom = parseString(body)
        return dom.getElementsByTagName('code')[0].firstChild.data
    else:
        return body

class SavePlaylistHandler(webapp.RequestHandler):
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

            playlist_id = plist_id_from_title(youtube_api, title)
            if playlist_id:
                #
                # Dammit YouTube API, why do you have to be so inconsistent?
                # playlist.id.text works for DeletePlaylist, doesn't work for
                # AddPlaylistVideoEntryToPlaylist.
                # Passing a URI works for APVETP but not for DeletePlaylist.
                # FFS...
                #
                response = youtube_api.DeletePlaylist(playlist_id)
                if not response:
                    raise gdata.service.Error, 'Could not delete playlist'

            new_playlistentry = youtube_api.AddPlaylist(title, description)
            if isinstance(new_playlistentry, gdata.youtube.YouTubePlaylistEntry):
                playlist_id = new_playlistentry.id.text.split('/')[-1]
            else:
                raise gdata.service.Error, 'Could not create playlist'

            plist_uri = PLAYLIST_URI + playlist_id
            plist_url = PLAYLIST_URL + playlist_id
            template_values = { 
                    'token': channel.create_channel(channel_id),
                    'plist_uri' : plist_uri, 
                    'plist_url' : plist_url,
                    'channel_id' : channel_id,
                    'limit' : limit }
        except gdata.service.Error, err:
            logging.error('gdata.service.Error' + str(err))
            template_values = { 
                    'token' : '', 
                    'error' : parse_request_error(err) }

        path = os.path.join(os.path.dirname(__file__), 'save_playlist.html')
        self.response.out.write(template.render(path, template_values))

class ChannelOpenedHandler(webapp.RequestHandler):
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
            params = { 
                    'plist_uri' : self.request.get('plist_uri'),
                    'channel_id' : self.request.get('channel_id'),
                    'limit': str(limit),
                    'url' : v.url,
                    'title' : v.title,
                    'permalink' : v.permalink,
                    'token' : str(pickle.dumps(token))
                }
            taskqueue.add(url='/spl_task', params=params)
        
class SavePlaylistTask(webapp.RequestHandler):
    """
    This is a task that gets put on the task queue by the Opened class.
    It performs the addition of a single video to some playlist.
    It communicates with the client-side JavaScript via the Channel API.
    """
    def post(self):
        channel_id = self.request.get('channel_id')
        plist_uri = self.request.get('plist_uri')
        video_id = self.request.get('video_id')
        url = self.request.get('url')
        title = self.request.get('title')
        permalink = self.request.get('permalink')

        #
        # It appears that it's impossible to use the OAuth decorators here, so
        # we pass the token through the POST parameters instead.  Unpickling
        # from Unicode seems to fail, so convert to regular string.
        #
        token_str = str(self.request.get('token'))
        token = pickle.loads(token_str)

        delay = 0.10
        payload = { 'url' : url } 
        video_id = vid_from_url(url)
        if not video_id:
            payload['error'] = 'skipped'
        else:
            try:
                youtube_api = youtube_login(token)
                #
                # If we've used up all of our quota, wait a little bit before
                # trying again.  The wait delay is doubled each time.  Give up
                # when the delay reaches 1 minute.
                #
                while True:
                    if delay > 60:
                        raise gdata.service.Error, 'exceeded max delay'
                    try:
                        plve = youtube_api.AddPlaylistVideoEntryToPlaylist(
                            plist_uri, video_id, title, permalink)
                        if not isinstance(
                                plve, 
                                gdata.youtube.YouTubePlaylistVideoEntry):
                            raise gdata.service.Error, 'bad instance'
                        break
                    except gdata.service.Error, err:
                        code = parse_request_error(err)
                        if code == 'too_many_recent_calls':
                            delay = delay*2
                            time.sleep(delay)
                            continue
                        else:
                            logging.error('gdata.service.Error' + str(err))
                            payload['error'] = code
                            break
            except gdata.service.Error, err:
                logging.error('gdata.service.Error' + str(err))
                payload['error'] = err[0]['reason']

        channel.send_message(channel_id, simplejson.dumps(payload))

application = webapp.WSGIApplication([
    ('/', WelcomeHandler),
    ('/start', MainPageHandler),
    ('/save_playlist', SavePlaylistHandler),
    ('/edit_playlist', EditPlaylistHandler),
    ('/spl_task', SavePlaylistTask),
    ('/opened', ChannelOpenedHandler)
], debug=True)

def main():
  run_wsgi_app(application)

if __name__ == '__main__':
  main()
