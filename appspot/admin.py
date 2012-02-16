from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import taskqueue
from google.appengine.ext import db
import logging

import datetime
import time
import urllib2

import reddit

USER_AGENT = 'http://rvytpl.appspot.com'

"""Fetch and keep this many entries from the subreddit."""
REDDIT_ENTRY_LIMIT = 100

"""Sleep after fetching this many entries."""
REDDIT_BATCH_SIZE = 25

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
        reddit_api = reddit.Reddit(user_agent=USER_AGENT)
        subreddit = reddit_api.get_subreddit('videos').get_top(
                limit=REDDIT_ENTRY_LIMIT)

        new_entries = { }
        for rank in range(REDDIT_ENTRY_LIMIT):
            # 
            # Sleep every 25 entries to increase the gap between Reddit API
            # calls (it fetches entries in batches of 25).
            #
            # subreddit.next() throws exceptions occasionally.  Most often, it's
            # a HTTP Error 429 (Unknown).  Rather than deal with it explicitly,
            # let the current update task fail.  It will be rescheduled
            # automatically by GAE.
            #
            if rank and (rank % REDDIT_BATCH_SIZE == 0):
                logging.info('Fetched %d entries, sleeping' % rank)
                time.sleep(60)
            entry = subreddit.next()
            new_entries[entry.id] = (rank, entry)

        #
        # Update/add entries to the data store.
        #
        timestamp = datetime.datetime.now()
        for entry_id, (rank,entry) in new_entries.items():
            entry_key = db.Key.from_path('RedditEntry', entry_id)
            store = db.get(entry_key)
            if store:
                store.rank = rank
                store.score = entry.score
                store.timestamp = timestamp
            else:
                store = RedditEntry(
                            key_name=entry.id,
                            rank=rank,
                            title=entry.title.replace('\n', ' '),
                            url=entry.url,
                            permalink=entry.permalink,
                            score=entry.score,
                            timestamp = timestamp)
                logging.info('adding new entry %s' % entry.url)
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
