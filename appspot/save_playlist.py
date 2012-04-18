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

import os

from common import CLIENT_SECRETS, USER_AGENT, YOUTUBE_DEVELOPER_KEY
from common import create_decorator
from admin import RedditEntry

decorator = create_decorator()

def parse_request_error(err):
    body = err[0]['body']
    if body.startswith("<?xml version='1.0' encoding='UTF-8'?>"):
        dom = parseString(body)
        return dom.getElementsByTagName('code')[0].firstChild.data
    else:
        return body

class StartPageHandler(webapp.RequestHandler):
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

