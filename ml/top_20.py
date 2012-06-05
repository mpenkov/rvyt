"""
Fetch the current top 20 YouTube videos on the subreddit.
For each video, grabs the actual video samples, YouTube context and Reddit
comments.
"""

import urllib
import json

LOCAL_JSON = 'rvideos.json'

import os.path as P

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
COMMENTS_JSON = '%s-comments.json'

for i,entry in enumerate(youtube):
    vid = VIDEO_ID.search(entry['data']['url']).group('video_id')
    #
    # Last character of permalink is a slash and we don't need that.
    #
    comment_file = COMMENTS_JSON % vid
    if not P.exists(comment_file):
        fin = urllib.urlopen(COMMENTS_URL % entry['data']['permalink'][:-1])
        comments_json = fin.read()
        fout = open(comment_file, 'w')
        fout.write(comments_json)
        fout.close()
    else:
        comments_json = open(comment_file).read()
    comments = json.loads(comments_json)

    print i, entry['data']['title']
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

print '\n'.join(video_ids)
