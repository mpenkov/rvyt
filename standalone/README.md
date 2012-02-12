# Introduction

This project grabs the top links on Reddit's /r/videos and turns them
into a YouTube playlist.  This way, you don't have to keep reaching for the
keyboard and mouse in between videos.  

# Configuration

The application configuration is stored in a plain text file called `rvyt.cfg'.
Open this file with a text editor before running the application for the first
time.

# About Passwords

Reddit supports anonymous browsing, so you don't need to specify your username
and password if you don't want to.  If you do, then the subreddit will be
personalized for you.

Providing the username and password is compulsory for YouTube (there is no way
to create a playlist without logging in first).

# Future features

 - Upvote the videos that you give a thumbs up for
 - Include links to the reddit permalink in the playlist comments (the API 
   allows this according to the documentation, but it doesn't seem to work in
   real life).
 - Option to exclude videos that you've already seen

# Acknowledgements

- Reddit API is by mellort (https://github.com/mellort/reddit_api.git)
- YouTube API is by Google (http://code.google.com/apis/youtube/1.0/developers_guide_python.html)
- The ProgressMeter code is by Michael Lange <klappnase (at) freakmail (dot)
  de> (http://tkinter.unpythonic.net/wiki/ProgressMeter)
- reddit.ico is from
  http://www.veryicon.com/icons/internet--web/aquaticus-social/reddit.html
  (Creative Commons Attribution-No Derivative Works 3.0)
