"""Save videos.pickle as a Youtube playlist."""

import gdata.youtube
import gdata.youtube.service
import time
import pickle

from get_videos import Entry

def create_parser(usage):
    """Create an object to use for the parsing of command-line arguments."""
    from optparse import OptionParser
    parser = OptionParser(usage)
    parser.add_option(
            '--debug', 
            '-d', 
            dest='debug', 
            default=False,
            action='store_true',
            help='Show debug information')
    parser.add_option(
            '--username',
            '-u',
            dest='user',
            type='string',
            help='Login using the specified username')
    parser.add_option(
            '--password',
            '-p',
            dest='passwd',
            type='string',
            help='Login using the specified password')
    parser.add_option(
            '--title',
            '-t',
            dest='title',
            type='string',
            default='Reddit videos',
            help='Add the videos to the playlist of the specified title')
    return parser

def main():
    parser = create_parser('usage: %s videos.pickle [options]' % __file__)
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error('invalid number of arguments')

    yt_service = gdata.youtube.service.YouTubeService()
    yt_service.developer_key = open('gitignore/youtube-key.txt').read().strip()
    yt_service.email = options.user
    yt_service.password = options.passwd
    yt_service.source = 'https://github.com/mpenkov/rvyt'
    yt_service.ProgrammaticLogin()

    playlist_feed = yt_service.GetYouTubePlaylistFeed()
    for pl in playlist_feed.entry:
        if pl.title.text == options.title:
            #
            # Dammit YouTube, why do you have to be so inconsistent?
            # playlist.id.text works for DeletePlaylist, doesn't work for
            # AddPlaylistVideoEntryToPlaylist.
            # Passing a URI wroks for APVETP but not for DeletePlaylist.
            # FFS...
            #
            response = yt_service.DeletePlaylist(pl.id.text)
            if response is True:
                print 'Playlist successfully deleted'
            else:
                assert False

    new_private_playlistentry = yt_service.AddPlaylist(
            options.title, 'a new private playlist', True)
    if isinstance(new_private_playlistentry, gdata.youtube.YouTubePlaylistEntry):
        playlist_entry_id = new_private_playlistentry.id.text.split('/')[-1]
        print 'New private playlist added', playlist_entry_id
    else:
        assert False

    playlist_uri = 'http://gdata.youtube.com/feeds/api/playlists/' + playlist_entry_id

    videos = pickle.load(open(args[0]))
    for i,v in enumerate(videos):
        if v.domain != 'youtube.com':
            print v.url, 'skipping'
            continue

        querystring = v.url.split('?')[-1]
        args = querystring.split(';')
        video_id = None

        try:
            for key,val in map(lambda f: f.split('='), args):
                if key == 'v':
                    video_id = str(val[:11])
                    break
        except ValueError:
            print v.url, 'skipping'
            continue
     
        #
        # FIXME: the last two arguments seem to be ignored.
        #
        playlist_video_entry = yt_service.AddPlaylistVideoEntryToPlaylist(
            playlist_uri, video_id, v.title, v.permalink)

        if isinstance(playlist_video_entry, gdata.youtube.YouTubePlaylistVideoEntry):
            print 'Video added', v.url

        #
        # Respect the API call limits.
        #
        time.sleep(1)

if __name__ == '__main__':
    import sys
    sys.exit(main())
