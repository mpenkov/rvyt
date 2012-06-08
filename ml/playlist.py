"""
Makes a playlist that can be played in VLC to perform classification.
Keeps track of what videos have been classified and excludes them from the
playlist.

The playlist is output to standard output.
"""
import os
import os.path as P

DATA_DIR = 'data'
VIEWED_CSV = 'labels.txt'

if P.isfile(VIEWED_CSV):
    viewed = [ l.split(' ')[0] 
            for l in open(VIEWED_CSV).read().strip().split('\n') ]
else:
    viewed = []

VIDEO_EXT = '.mp4', '.webm', '.flv'

videos = filter(
        lambda f: P.splitext(f.lower())[1] in VIDEO_EXT and f not in viewed, 
        os.listdir(DATA_DIR))

print '[Playlist]'
for i,name in enumerate(videos):
    print 'File%d=%s' % (i+1, P.join(DATA_DIR, name))
print 'NumberOfEntries=%d' % len(videos)
