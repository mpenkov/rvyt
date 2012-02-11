import os
import cgi
import datetime
import random
import urllib
import urlparse
import time
import wsgiref.handlers
import simplejson

import reddit

from google.appengine.api import channel
from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

import gdata.youtube
import gdata.youtube.service
import gdata.service

#
# TODO: <shameless_copy_paste>
#

USER_AGENT = 'http://rvytpl.appspot.com'
YOUTUBE_DEVELOPER_KEY = 'AI39si4TTIXb-M4G0rhm4kG1eYowjK2tlHZlrxGS4vOegXEK0oS3LRrmx-PMbrMRVtfHqpJ6gG60qQ2U4w6X_DnqfmkuqtTDvA'

def youtube_login(user, passwd):
    yt_service = gdata.youtube.service.YouTubeService()
    yt_service.developer_key = YOUTUBE_DEVELOPER_KEY
    yt_service.email = user
    yt_service.password = passwd
    yt_service.source = USER_AGENT
    yt_service.ProgrammaticLogin()
    return yt_service

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
    playlist_feed = youtube_api.GetYouTubePlaylistFeed()
    for pl in playlist_feed.entry:
        if pl.title.text == title:
            return pl.id.text
    return None

def reddit_login(user, passwd):
    r = reddit.Reddit(user_agent=USER_AGENT)
    if user and passwd:
        r.login(user, passwd)
    return r

#
# TODO: </shameless_copy_paste>
#

class MainPage(webapp.RequestHandler):
    def get(self):
        if users.get_current_user():
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = { 'url': url }
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))

class Make(webapp.RequestHandler):
    def post(self):
        user = self.request.get('user')
        passwd = self.request.get('passwd')
        title = self.request.get('title')
        description = self.request.get('description')
        limit = self.request.get('limit')

        channel_id = str(random.randint(1,10000))+str(datetime.datetime.now())

        template_values = { 'token': channel.create_channel(channel_id) }
        path = os.path.join(os.path.dirname(__file__), 'make.html')
        self.response.out.write(template.render(path, template_values))

        params = { 
                'user': user,
                'passwd': passwd,
                'title': title,
                'description': description,
                'channel_id': channel_id,
                'limit': limit
                }
        taskqueue.add(url='/worker', params=params)
        
class Worker(webapp.RequestHandler):
    def post(self):
        user = self.request.get('user')
        passwd = self.request.get('passwd')
        channel_id = self.request.get('channel_id')
        title = self.request.get('title')
        description = self.request.get('description')
        limit = int(self.request.get('limit'))

        channel.send_message(
                channel_id, 
                simplejson.dumps({ 'status' : 'logging into Reddit'}))
        reddit_api = reddit_login(None, None)

        channel.send_message(
                channel_id, 
                simplejson.dumps({ 'status' : 'logging into YouTube'}))
        try:
            youtube_api = youtube_login(user, passwd)
        except gdata.service.Error, e:
            #
            # Probably a 403...
            #
            channel.send_message(
                    channel_id, 
                    simplejson.dumps({ 'status' : 'login failed (%s)' % e }))
            return


        channel.send_message(
                channel_id, 
                simplejson.dumps({ 'status' : 'fetching subreddit'}))

        subreddit = reddit_api.get_subreddit('videos').get_top(limit=limit)
        entries = []
        while True:
            try:                
                #
                # FIXME: this fails occasionally with a weird Error 429...
                #
                entries.append(subreddit.next())
            except StopIteration:
                break

        entries.sort(key=lambda f: f.score, reverse=True)

        channel.send_message(
                channel_id, 
                simplejson.dumps({ 'status' : 'querying YouTube playlists'}))
        playlist_id = get_playlist_id_from_title(youtube_api, title)
        if playlist_id:
            #
            # Dammit YouTube API, why do you have to be so inconsistent?
            # playlist.id.text works for DeletePlaylist, doesn't work for
            # AddPlaylistVideoEntryToPlaylist.
            # Passing a URI wroks for APVETP but not for DeletePlaylist.
            # FFS...
            #
            channel.send_message(
                    channel_id, 
                    simplejson.dumps({ 'status' : 'deleting old playlist'}))
            response = youtube_api.DeletePlaylist(playlist_id)
            if not response:
                #
                # TODO: message to client
                #
                raise RuntimeError(
                        'Unable to delete existing playlist: %s' % title)

        #channel.send_message(channel_id, 'Creating playlist')

        channel.send_message(
                channel_id, 
                simplejson.dumps({ 'status' : 'creating new playlist' }))
        new_playlistentry = youtube_api.AddPlaylist(title, description)
        if isinstance(new_playlistentry, gdata.youtube.YouTubePlaylistEntry):
            playlist_id = new_playlistentry.id.text.split('/')[-1]
        else:
            #
            # TODO: message to client
            #
            raise RuntimeError('Unable to create new playlist: %s' % title)

        playlist_uri = 'http://gdata.youtube.com/feeds/api/playlists/' + playlist_id

        result = []
        
        #channel.send_message(channel_id, 'Fetching entries')

        for i,v in enumerate(entries):
            #
            # FIXME: calls inside this loop can fail with 
            # "too many recent calls".  Need to handle that exception as 
            # otherwise it will force a restart of the task, which is not
            # good.
            #
            video_id = get_video_id_from_url(v.url)
            if video_id:
                #
                # FIXME: the last two arguments seem to be ignored.
                #
                playlist_video_entry = youtube_api.AddPlaylistVideoEntryToPlaylist(
                    playlist_uri, video_id, v.title, v.permalink)

                if not isinstance(playlist_video_entry, 
                        gdata.youtube.YouTubePlaylistVideoEntry):
                    #
                    # TODO: message to client
                    #
                    raise RuntimeError('Unable to create new video entry')
                channel.send_message(channel_id,
                    simplejson.dumps({ 'video_url' : v.url, 'status': 'OK' }))
            else:
                channel.send_message(channel_id,
                    simplejson.dumps({ 'video_url' : v.url, 'status': 'skipped'}))

            #
            # Respect the API call limits.
            #
            time.sleep(1.0)

        plist_url = 'http://www.youtube.com/playlist?list=' + playlist_id
        channel.send_message(
                channel_id, 
                simplejson.dumps({ 
                    'status' : 'finished', 'plist_url' : plist_url
                     }
                ))
        #channel.send_message(channel_id, 'All done')

application = webapp.WSGIApplication([
  ('/', MainPage),
  ('/make', Make),
  ('/worker', Worker)
], debug=True)


def main():
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
