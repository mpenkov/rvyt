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

Providing the username and password is compulsory for YouTube.

# Future features:

 - Upvote the videos that you give a thumbs up for
 - Include links to the reddit permalink in the playlist comments (the API 
   allows this according to the documentation, but it doesn't seem to work in
   real life).
 - Option to exclude videos that you've already seen
