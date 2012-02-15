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
    rank = db.IntegerProperty(required=True)
    title = db.StringProperty(required=True)
    url = db.StringProperty(required=True)
    permalink = db.StringProperty(required=True)
    score = db.IntegerProperty(required=True)

class UpdateTimestamp(db.Model):
    """An entity to hold information about when we last updated."""
    timestamp = db.DateTimeProperty(required=True)

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
            if rank and (rank % REDDIT_BATCH_SIZE == 0):
                time.sleep(60)
            entry = subreddit.next()
            new_entries[entry.url] = (rank, entry)
            logging.info('fetched entry %d' % rank)

        query = RedditEntry.all()
        old_entries = query.fetch(REDDIT_ENTRY_LIMIT)

        to_update = { }
        for oe in old_entries:
            if oe.url not in new_entries:
                logging.info('deleting old entry %s' % oe.url)
                oe.delete()
            else:
                to_update[oe.url] = oe

        for entry_url, (rank,entry) in new_entries.items():
            try:
                store = to_update[entry_url]
                store.rank = rank
                store.score = entry.score
            except KeyError:
                logging.info('adding new entry %s' % entry.url)
                store = RedditEntry(
                            rank=rank,
                            title=entry.title.replace('\n', ' '),
                            url=entry.url,
                            permalink=entry.permalink,
                            score=entry.score)
            store.put()

        query = UpdateTimestamp.all()
        for uts in query.fetch(1):
            uts.delete()
        uts = UpdateTimestamp(timestamp=datetime.datetime.now())
        uts.put()

application = webapp.WSGIApplication([
    ('/admin/update', UpdateHandler),
    ('/admin/update_task', UpdateTask),
], debug=True)

def main():
  run_wsgi_app(application)

if __name__ == '__main__':
  main()
