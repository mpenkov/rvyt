from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import taskqueue
from google.appengine.ext import db
import logging

import datetime
import time
import urllib2
import simplejson

USER_AGENT = 'http://rvytpl.appspot.com'

"""Fetch and keep this many entries from the subreddit."""
REDDIT_ENTRY_LIMIT = 100

RVIDEOS_URL = 'http://www.reddit.com/r/videos.json'

class RedditEntry(db.Model):
    """An entity to hold information about a single Reddit entry."""
    rank = db.IntegerProperty()
    title = db.StringProperty()
    url = db.StringProperty()
    permalink = db.StringProperty()
    score = db.IntegerProperty()
    timestamp = db.DateTimeProperty()

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

        #
        # Update/add entries to the data store.
        #
        timestamp = datetime.datetime.now()
        for rank, entry in enumerate(new_entries):
            entry_key = db.Key.from_path('RedditEntry', entry['id'])
            store = db.get(entry_key)

            if store:
                store.rank = rank
                store.score = entry['score']
                store.timestamp = timestamp
                logging.info('updating entry %s' % entry['url'])
            else:
                store = RedditEntry(
                            key_name=entry['id'],
                            rank=rank,
                            title=entry['title'].replace('\n', ' '),
                            url=entry['url'],
                            permalink=entry['permalink'],
                            score=entry['score'],
                            timestamp = timestamp)
                logging.info('adding new entry %s' % entry['url'])
            store.put()

        #
        # Delete stale entries.
        #
        query = RedditEntry.all()
        query.filter('timestamp <', timestamp)
        to_delete = [ x for x in query ]
        logging.info('deleting %d entries' % len(to_delete))
        db.delete(to_delete)

application = webapp.WSGIApplication([
    ('/admin/update', UpdateHandler),
    ('/admin/update_task', UpdateTask),
], debug=True)

def main():
  run_wsgi_app(application)

if __name__ == '__main__':
  main()
