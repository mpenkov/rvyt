"""
Fetch the current top 20 YouTube videos on the subreddit.
For each video, grabs the actual video samples, YouTube context and Reddit
comments.
"""

import urllib
import json

import os.path as P
import datetime

DATA_DIR = 'data'
LOCAL_JSON = P.join(
        DATA_DIR, 
        'top20-%s.json' % datetime.date.today().isoformat())

#
# Only query Reddit once a day.
#
if not P.isfile(LOCAL_JSON):
    fin = urllib.urlopen('http://www.reddit.com/r/videos.json')
    fout = open(LOCAL_JSON, 'w')
    json_str = fin.read()
    fout.write(json_str)
    fout.close()
else:
    json_str = open(LOCAL_JSON).read()

import re
VIDEO_ID = re.compile(r'v=(?P<video_id>[\d\w_-]{11})')

parsed = json.loads(json_str)
entries = parsed['data']['children']
youtube = filter(lambda f: f['data']['domain'].find('youtube') != -1, entries)

video_ids = []

COMMENTS_URL = 'http://www.reddit.com/%s.json'
COMMENTS_JSON = P.join(DATA_DIR, '%s.json')

for i,entry in enumerate(youtube):
    entry_id = entry['data']['id']
    vid = VIDEO_ID.search(entry['data']['url']).group('video_id')
    comment_file = COMMENTS_JSON % entry_id
    #
    # Only query each Reddit item once.  The result is stored as 
    # JSON for later work.
    #
    if not P.exists(comment_file):
        #
        # Last character of permalink is a slash and we don't need that.
        #
        fin = urllib.urlopen(COMMENTS_URL % entry['data']['permalink'][:-1])
        comments_json = fin.read()
        fout = open(comment_file, 'w')
        fout.write(comments_json)
        fout.close()
    else:
        comments_json = open(comment_file).read()
    comments = json.loads(comments_json)

    if False:
        print i, entry['data']['title']
        #
        # TODO: use this when I actually want to parse the JSON stuff.
        # 

        for comment in comments:
            try:
                for j,comment2 in enumerate(comment['data']['children']):
                    print '\t', j, comment2['data']['body'][:60]
            except AttributeError:
                print comment
            except KeyError:
                print 'KeyError'
            except TypeError:
                print comment

    video_ids.append(vid)

#
# Pipe the result to a text file and then use something like:
#
# for /f %a in ( video_ids.txt ) do python youtube-dl.py %a --output data/%(id)s.%(ext)s
#
# to fetch the videos.
#
print '\n'.join(video_ids)
