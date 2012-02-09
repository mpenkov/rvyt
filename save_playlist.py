"""Save videos.pickle as a Youtube playlist."""

import gdata.youtube
import gdata.youtube.service

from get_videos import Entry

TITLE = 'foo'

user, passwd = open('gitignore/youtube.txt').read().strip().split('\n')
yt_service = gdata.youtube.service.YouTubeService()
yt_service.developer_key = open('gitignore/youtube-key.txt').read().strip()
yt_service.email = user
yt_service.password = passwd
yt_service.source = 'https://github.com/mpenkov/rvyt'
yt_service.ProgrammaticLogin()

playlist = None
playlist_feed = yt_service.GetYouTubePlaylistFeed()
for pl in playlist_feed.entry:
    if pl.title.text == TITLE:
        playlist = pl
        break

if playlist:
    #
    # Dammit YouTube, why do you have to be so inconsistent?
    # playlist.id.text works for DeletePlaylist, doesn't work for
    # AddPlaylistVideoEntryToPlaylist.
    # Passing a URI wroks for APVETP but not for DeletePlaylist.
    # FFS...
    #
    response = yt_service.DeletePlaylist(playlist.id.text)
    if response is True:
        print 'Playlist successfully deleted'
    else:
        assert False

new_private_playlistentry = yt_service.AddPlaylist(
        TITLE, 'a new private playlist', True)
if isinstance(new_private_playlistentry, gdata.youtube.YouTubePlaylistEntry):
    playlist_entry_id = new_private_playlistentry.id.text.split('/')[-1]
    print 'New private playlist added', playlist_entry_id
else:
    assert False

playlist_uri = 'http://gdata.youtube.com/feeds/api/playlists/' + playlist_entry_id

import pickle
videos = pickle.load(open('videos.pickle'))
for v in videos:
    querystring = v.url.split('?')[-1]
    args = querystring.split(';')
    video_id = None
    if v.domain != 'youtube.com':
        print v.url, 'skipping'
        continue

    for key,val in map(lambda f: f.split('='), args):
        if key == 'v':
            video_id = str(val[:11])
            break
 
    #
    # FIXME: the last two arguments seem to be ignored.
    #
    playlist_video_entry = yt_service.AddPlaylistVideoEntryToPlaylist(
        playlist_uri, video_id, v.title, v.permalink)

    if isinstance(playlist_video_entry, gdata.youtube.YouTubePlaylistVideoEntry):
        print 'Video added', v.url
