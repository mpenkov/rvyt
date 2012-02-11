import os
import cgi
import datetime
import urllib
import urlparse
import time
import wsgiref.handlers

import reddit

from google.appengine.api import channel
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

import gdata.youtube
import gdata.youtube.service
import gdata.service

USER_AGENT = 'http://rvytpl.appspot.com'
YOUTUBE_DEVELOPER_KEY = 'AI39si4TTIXb-M4G0rhm4kG1eYowjK2tlHZlrxGS4vOegXEK0oS3LRrmx-PMbrMRVtfHqpJ6gG60qQ2U4w6X_DnqfmkuqtTDvA'

#
# TODO: <shameless_copy_paste>
#
def youtube_login(user, passwd):
    yt_service = gdata.youtube.service.YouTubeService()
    yt_service.developer_key = YOUTUBE_DEVELOPER_KEY
    yt_service.email = user
    yt_service.password = passwd
    yt_service.source = USER_AGENT
    yt_service.ProgrammaticLogin()
    return yt_service

def reddit_login(user, passwd):
    r = reddit.Reddit(user_agent=USER_AGENT)
    if user and passwd:
        r.login(user, passwd)
    return r

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

def save_playlist(youtube_api, entries, title, description):
    playlist_feed = youtube_api.GetYouTubePlaylistFeed()
    for pl in playlist_feed.entry:
        if pl.title.text == title:
            #
            # Dammit YouTube API, why do you have to be so inconsistent?
            # playlist.id.text works for DeletePlaylist, doesn't work for
            # AddPlaylistVideoEntryToPlaylist.
            # Passing a URI wroks for APVETP but not for DeletePlaylist.
            # FFS...
            #
            response = youtube_api.DeletePlaylist(pl.id.text)
            if not response:
                raise RuntimeError(
                        'Unable to delete existing playlist: %s' % title)

    new_private_playlistentry = youtube_api.AddPlaylist(
            title, description)
    if isinstance(
            new_private_playlistentry, gdata.youtube.YouTubePlaylistEntry):

        playlist_entry_id = new_private_playlistentry.id.text.split('/')[-1]
    else:
        raise RuntimeError('Unable to create new playlist: %s' % title)

    playlist_uri = 'http://gdata.youtube.com/feeds/api/playlists/' + playlist_entry_id

    result = []

    for i,v in enumerate(entries):
        video_id = get_video_id_from_url(v.url)
        if video_id:
            #
            # FIXME: the last two arguments seem to be ignored.
            #
            playlist_video_entry = youtube_api.AddPlaylistVideoEntryToPlaylist(
                playlist_uri, video_id, v.title, v.permalink)

            if not isinstance(playlist_video_entry, 
                    gdata.youtube.YouTubePlaylistVideoEntry):
                raise RuntimeError('Unable to create new video entry')
            result.append((v.url, 'OK'))
        else:
            result.append((v.url, 'skipped'))

        #
        # Respect the API call limits.
        #
        time.sleep(1.0)

    return playlist_entry_id, result

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

        #
        # TODO: better tokens...  
        #
        token = channel.create_channel('foo')
        template_values = { 'url': url, 'token': token }

        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))

class Make(webapp.RequestHandler):
    def post(self):
        user = self.request.get('user')
        passwd = self.request.get('passwd')
        reddit_api = reddit_login(None, None)
        youtube_api = youtube_login(user, passwd)
        limit = int(self.request.get('limit'))
        subreddit = reddit_api.get_subreddit('videos').get_top(limit=limit)
        entries = []
        while True:
            try:                
                entries.append(subreddit.next())
            except StopIteration:
                break

        entries.sort(key=lambda f: f.score, reverse=True)
        
        title = self.request.get('title')
        description = self.request.get('description')
        pid, results = save_playlist(youtube_api, entries, title, description)

        playlist_url = 'http://www.youtube.com/playlist?list=%s' % pid
        template_values = { 'playlist_url' : playlist_url, 'results': results }

        path = os.path.join(os.path.dirname(__file__), 'make.html')
        self.response.out.write(template.render(path, template_values))

application = webapp.WSGIApplication([
  ('/', MainPage),
  ('/make', Make)
], debug=True)


def main():
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
