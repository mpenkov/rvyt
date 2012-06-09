from top_20 import DATA_DIR, VIDEO_ID

import json

import os
import os.path as P

json_files = filter(
        lambda f: not f.startswith('top20') and f.endswith('.json'), 
        os.listdir(DATA_DIR))

lines = open('labels.txt').read().strip().split('\n')
yval = {}
for line in lines:
    video_file, y = line.split(' ')
    video_id, _ = P.splitext(video_file)
    yval[video_id] = y

#print yval

class Entry:
    """Data holder for an entry."""
    def __init__(self, json_str):
        parsed = json.loads(json_str)
        #
        # FFS...
        #
        media = parsed[0]['data']['children'][0]['data']

        self.id = media['id']
        self.ups = int(media['ups'])
        self.downs = int(media['downs'])
        self.title = media['title']
        self.video_id = VIDEO_ID.search(media['url']).group('video_id')
        self.over_18 = 1 if media['over_18'] else 0
        self.num_comments = int(media['num_comments'])

        self.all_comments = flatten_comments(parsed[1]['data']['children'])

class Comment:
    """Data holder for a comment."""
    def __init__(self, body, ups, downs):
        self.body = body
        self.ups = ups
        self.downs = downs

    def __str__(self):
        body = self.body
        if len(body) > 60:
            body = body[:60] + '...'
        return '+%d -%d `%s\'' % (self.ups, self.downs, body)

def flatten_comments(root_comments):
    """
    Flatten comments into a list of Comment objects using a tree traversal.
    """
    all_comments = []
    nodes = root_comments[:]
    while nodes:
        node = nodes.pop()
        data = node['data']
        if 'body' not in data:
            #
            # weird child node
            #
            continue
        comment = Comment(data['body'], int(data['ups']), int(data['downs']))
        all_comments.append(comment)
        if data['replies']:
            for reply in data['replies']['data']['children']:
                nodes.append(reply)
    return all_comments

import pickle
import sys

categories = ['Animals', 'Autos', 'Comedy', 'Education', 'Entertainment', 
    'Film', 'Games', 'Howto', 'Music', 'News', 'Nonprofit', 'People', 
    'Sports', 'Tech', 'Travel']

for f in json_files:
    e = Entry(open(P.join(DATA_DIR, f)).read().strip())
    pickle_file = P.join(DATA_DIR, e.video_id + '.pickle')
    if not P.isfile(pickle_file):
        print >> sys.stderr, 'missing file: %s for entry: %s' % (pickle_file, e.id)
        continue

    yt = pickle.load(open(pickle_file))
    if yt.statistics:
        views = int(yt.statistics.view_count)
    else:
        views = 0

    if yt.rating:
        rating = yt.rating.average
    else:
        rating = 0

    category = categories.index(yt.media.category[0].text)

    features = [ f, e.video_id, e.ups, e.downs, e.over_18, e.num_comments, 
            views, rating, category ]

    if e.video_id in yval:
        print ' '.join(map(str, features)), yval[e.video_id]
    else:
        print >> sys.stderr, 'missing yvalue: %s for entry: %s' % (pickle_file, e.id)
