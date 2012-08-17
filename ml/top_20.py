"""
Fetch the current top 20 YouTube videos on the subreddit.
For each video, grabs the actual video samples, YouTube context and Reddit
comments.
"""

import urllib
import urllib2
import json

import os
import os.path as P
import datetime

import re
import sys

DATA_DIR = 'data'
LOCAL_JSON = P.join(
        DATA_DIR, 
        'top20-%s.json' % datetime.date.today().isoformat())
VIDEO_ID = re.compile(r'v=(?P<video_id>[\d\w_-]{11})')

COMMENTS_URL = 'http://www.reddit.com/%s.json'
COMMENTS_JSON = P.join(DATA_DIR, '%s.json')

USER_AGENT = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
HEADERS = { 'User-Agent' : USER_AGENT }
VALUES = { }

DATA = urllib.urlencode(VALUES)

def main():
    #
    # Only query Reddit once a day.
    #
    if not P.isfile(LOCAL_JSON):
        url = 'http://www.reddit.com/r/videos.json'
        print >> sys.stderr, url
        req = urllib2.Request(url, DATA, HEADERS)
        response = urllib2.urlopen(req)

        fout = open(LOCAL_JSON, 'w')
        json_str = response.read()
        fout.write(json_str)
        fout.close()
    else:
        json_str = open(LOCAL_JSON).read()

    parsed = json.loads(json_str)
    try:
        entries = parsed['data']['children']
    except KeyError:
        #
        # Bad JSON file, delete it and exit.
        # 
        print >> sys.stderr, 'Bad JSON file, try again.'
        os.remove(LOCAL_JSON)
        sys.exit(1)

    youtube = filter(lambda f: f['data']['domain'].find('youtube') != -1, entries)

    video_ids = []

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
            while True:
                url = COMMENTS_URL % entry['data']['permalink'][:-1]
                req = urllib2.Request(url, DATA, HEADERS)

                response = urllib2.urlopen(req)
                comments_json = response.read()
                if (comments_json.startswith('{"error": 429}')):
                    #
                    # We're being rate-limited.  Wait a little bit of time before 
                    # trying again.
                    #
                    time.sleep(10)
                    continue
                fout = open(comment_file, 'w')
                fout.write(comments_json)
                fout.close()
                break
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

if __name__ == '__main__':
    main()
