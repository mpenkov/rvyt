from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import taskqueue
from google.appengine.ext import db
import logging

import gdata.youtube
import gdata.youtube.service
import gdata.service

import datetime
import time
import urllib2
import urlparse
import simplejson

USER_AGENT = 'http://rvytpl.appspot.com'

"""Fetch and keep this many entries from the subreddit."""
REDDIT_ENTRY_LIMIT = 100

RVIDEOS_URL = 'http://www.reddit.com/r/videos.json'

def vid_from_url(url):
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
            #
            # http://www.youtube.com/watch?v=WTGUjRJiqik
            #
            for key,val in map(lambda f: f.split('='), args):
                if key == 'v':
                    return val[:11]
        except ValueError:
            pass

        if compo[-2] == 'v':
            #
            # http://www.youtube.com/v/WTGUjRJiqik
            #
            return compo[-1]
        return None
    else:
        return None


class RedditEntry(db.Model):
    """An entity to hold information about a single Reddit entry."""
    rank = db.IntegerProperty()
    title = db.StringProperty()
    url = db.StringProperty()
    permalink = db.StringProperty()
    score = db.IntegerProperty()
    timestamp = db.DateTimeProperty()
    thumbnail = db.StringProperty()
    #description = db.StringProperty()

MAX_STRLEN = 500

class YouTubeEntry(db.Model):
    video_id = db.StringProperty()
    category = db.StringProperty()
    keywords = db.StringProperty()

class UpdateHandler(webapp.RequestHandler):
    """Put an UpdateTask on the task queue."""
    def get(self):
        #
        # TODO: what if somebody is reading from the data store as 
        # we're refreshing?
        #
        taskqueue.add(url='/admin/update_task', params={})
        self.response.out.write('Scheduled UpdateTask')

class UpdateTask(webapp.RequestHandler):
    """Pull REDDIT_ENTRY_LIMIT entries from /r/videos into the data store."""
    def post(self):
        logging.info('UpdateTask started')

        after = None
        headers = { 'User-Agent' : USER_AGENT }
        new_entries = []
        while len(new_entries) < REDDIT_ENTRY_LIMIT:
            try:
                url = RVIDEOS_URL
                if after:
                    url += '?after=' + after
                request = urllib2.Request(url, headers=headers)
                json = simplejson.load(urllib2.urlopen(request))
                new_entries += [ foo['data'] 
                        for foo in json['data']['children'] ]
                after = json['data']['after']
            except urllib2.HTTPError, err:
                logging.error(err)

            #
            # TODO:
            # Ideally, we'd defer to another task on the queue, but it's simpler
            # to do this for now.
            #
            time.sleep(2)

        yt_service = gdata.youtube.service.YouTubeService()

        #
        # Update/add entries to the data store.
        #
        timestamp = datetime.datetime.now()
        for rank, entry in enumerate(new_entries):
            entry_key = db.Key.from_path('RedditEntry', entry['id'])
            reddit_store = db.get(entry_key)

            if reddit_store:
                reddit_store.rank = rank
                reddit_store.score = entry['score']
                reddit_store.timestamp = timestamp
                logging.info('updating entry %s' % entry['url'])
            else:
                reddit_store = RedditEntry(
                        key_name=entry['id'],
                        rank=rank,
                        title=entry['title'].replace('\n', ' '),
                        url=entry['url'],
                        permalink=entry['permalink'],
                        score=entry['score'],
                        thumbnail=entry['thumbnail'],
                        timestamp = timestamp)
                video_id = vid_from_url(reddit_store.url)
                if video_id:
                    youtube_video = yt_service.GetYouTubeVideoEntry(
                            video_id=video_id) 

                    try:
                        tags = youtube_video.media.keywords.text[:MAX_STRLEN]
                        try:
                            foo = unicode(tags).encode('utf-8')
                        except UnicodeDecodeError:
                            raise TypeError
                    except TypeError:
                        tags = ''
                    
                    try:
                        category = youtube_video.media.category[0].text
                    except TypeError:
                        category = ''

                    youtube_store = YouTubeEntry( 
                            video_id=video_id, 
                            category=category, 
                            keywords=tags)
                    youtube_store.put()
                logging.info('adding new entry %s' % entry['url'])
            reddit_store.put()

        #
        # Delete stale entries.
        #
        query = RedditEntry.all()
        query.filter('timestamp <', timestamp)
        to_delete = [ x for x in query ]
        db.delete(to_delete)
        logging.info('deleted %d reddit entries' % len(to_delete))

        video_ids = filter(
                lambda x: x, 
                [ vid_from_url(x.url) for x in to_delete ] )
        query = YouTubeEntry.all()
        query.filter('video_id in', video_ids)
        to_delete = [ x for x in query ]
        db.delete(to_delete)
        logging.info('deleted %d youtube entries' % len(to_delete))

application = webapp.WSGIApplication([
    ('/admin/update', UpdateHandler),
    ('/admin/update_task', UpdateTask),
], debug=True)

def main():
  run_wsgi_app(application)

if __name__ == '__main__':
  main()
