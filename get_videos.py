"""Fetch some videos from r/videos and serialize them."""

import reddit
user, passwd = open('gitignore/reddit.txt').read().strip().split('\n')
r = reddit.Reddit(user_agent='https://github.com/mpenkov/rvyt')
r.login(user, passwd)
entries = r.get_subreddit('videos').get_top(limit=10)

class Entry:
    """Serializable reddit.Submission."""
    def __init__(self, submission):
        for a in dir(submission):
            #
            # Don't worry about private attributes.  Also, some of the comment
            # attributes aren't friendly with getattr, so ignore them as well.
            #
            if a[0] == '_' or a.find('comments') != -1:
                continue
            v = getattr(submission, a)
            if type(v) in [ type(foo) for foo in [ 1, True, 'foo', u'foo' ] ]:
                setattr(self, a, v)

to_dump = []
while True:
    try:
        to_dump.append(Entry(entries.next()))
    except StopIteration:
        break

import pickle
fout = open('videos.pickle', 'w')
pickle.dump(to_dump, fout)
fout.close()
