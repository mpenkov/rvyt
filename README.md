# Introduction

This project the top links on Reddit's /r/videos and turns them
into a Youtube playlist.  This way, you don't have to keep reaching for the
keyboard and mouse in between videos.  It completely ignores non-Youtube videos.

    python get_videos.py videos.pickle

    python save_playlist.py videos.pickle -u your.email@gmail.com -p password

Reddit supports anonymous browsing, so you don't need to specify your username
and password if you don't want to.  If you do, then the subreddit will be
personalized for you.

Providing the username and password is compulsory for Youtube.

# Future features:

 - Upvote the videos that you give a thumbs up for
 - Include links to the reddit permalink in the playlist comments (the API 
   allows this according to the documentation, but it doesn't seem to work in
   real life).
 - Sort videos according to number upvotes, etc
 - Exclude videos that you've already seen
