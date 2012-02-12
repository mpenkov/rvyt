from Tkinter import *
import ImageTk
import tkMessageBox
import PIL.Image
from ProgressMeter import Meter

import reddit
import urllib2
import gdata.youtube
import gdata.youtube.service
import gdata.service
import threading
import Queue
import time
import ConfigParser
import urlparse

USER_AGENT = 'https://github.com/mpenkov/rvyt'

#
# TODO: get a new key for this application.
#
YOUTUBE_DEVELOPER_KEY = 'AI39si7lnm9bcrVuwNa2p58l0KhqPvPgTKMm6K-Bi1ZzVaDNvqbiEvrZJZfFfpMvMhJfOyaDtIpqTcHu6Xrj5121B8aRXNI76A'

def youtube_login(user,passwd):
    yt_service = gdata.youtube.service.YouTubeService()
    yt_service.developer_key = YOUTUBE_DEVELOPER_KEY
    yt_service.email = user
    yt_service.password = passwd
    yt_service.source = USER_AGENT
    yt_service.ProgrammaticLogin()
    return yt_service

def get_video_id_from_url(url):
    """
    If the specified URL is a YouTube video, returns the video ID.
    Otherwise, returns None.
    """
    p = urlparse.urlparse(url)
    compo = p.path.split('/')
    if p.netloc in [ 'www.youtu.be', 'youtu.be' ]:
        return compo[1]
    elif p.netloc in [ 'www.youtube.com', 'youtube.com' ]:
        args = p.query.split(';')
        video_id = None
        for key,val in map(lambda f: f.split('='), args):
            if key == 'v':
                return val[:11]
        return None
    else:
        return None

class RvytGUI(Frame):
    """A Frame that contains all the controls for the application."""
    def __init__(self, parent, config):
        Frame.__init__(self, parent)
        self.config = config

        self.progress = Meter(self, relief='ridge', width=150, bd=3)
        self.progress.grid(row=10,column=0,columnspan=4)
        self.btn_start = Button(self, text='start', 
                width=10, command=self.__handle_start)
        self.btn_start.grid(row=10,column=4,sticky=E)

        self.error_queue = Queue.Queue()
        self.message_queue = Queue.Queue()

    def __handle_start(self):
        """Handler for the start button."""
        self.__enable_input(False)
        self.thread = threading.Thread(target=self.__worker)
        self.thread.start()
        self.after(10, self.__check_completion)

    def __worker(self):
        """This is the function that runs inside the worker thread."""
        try:
            self.message_queue.put(('Logging into Reddit', 0.0))
            try:
                self.r = reddit.Reddit(user_agent=USER_AGENT)
                user = self.config.get('reddit', 'user')
                passwd = self.config.get('reddit', 'password')
                if user and passwd:
                    self.r.login(user, passwd)
            except urllib2.URLError:
                self.error_queue.put(('Reddit login failed', 
                    'Check the configuration file and\nrestart the application'))
                return

            self.message_queue.put(('Logging into YouTube', 0.0))
            try:
                self.yt = youtube_login(self.config.get('youtube', 'user'), 
                        self.config.get('youtube', 'password'))
            except (gdata.service.Error, gdata.service.CaptchaRequired) as err:
                self.error_queue.put(('YouTube login failed', str(err)))
                return

            self.message_queue.put(('Fetching submissions', 0.0))
            limit = int(self.config.get('reddit', 'limit'))
            subreddit = self.r.get_subreddit('videos').get_top(limit=limit)
            entries = []
            while True:
                try:                
                    entries.append(subreddit.next())
                except StopIteration:
                    break

            entries.sort(key=lambda f: f.score, reverse=True)

            self.__save_playlist(entries)
        except ConfigParser.NoOptionError, noe:
            self.error_queue.put(('Error parsing configuration file', 
                str(noe)))

    def __save_playlist(self, entries):
        self.message_queue.put(('Saving playlist', 0.0))
        title = self.config.get('youtube', 'title')
        description = self.config.get('youtube', 'description')

        playlist_feed = self.yt.GetYouTubePlaylistFeed()
        for pl in playlist_feed.entry:
            if pl.title.text == title:
                #
                # Dammit YouTube, why do you have to be so inconsistent?
                # playlist.id.text works for DeletePlaylist, doesn't work for
                # AddPlaylistVideoEntryToPlaylist.
                # Passing a URI wroks for APVETP but not for DeletePlaylist.
                # FFS...
                #
                response = self.yt.DeletePlaylist(pl.id.text)
                if response is True:
                    self.message_queue.put(('Deleted old playlist', 0.0))
                else:
                    self.error_queue.put(('Error saving playlist to YouTube', 
                        'Could not delete existing playlist `%s\'' % title))
                    return

        new_private_playlistentry = self.yt.AddPlaylist(
                title, description, True)
        if isinstance(new_private_playlistentry, gdata.youtube.YouTubePlaylistEntry):
            playlist_entry_id = new_private_playlistentry.id.text.split('/')[-1]
            self.message_queue.put(('Created new playlist', 0.0))
        else:
            self.error_queue.put(('Error saving playlist to YouTube', 
                'Could not create new playlist `%s\'' % title))

        playlist_uri = 'http://gdata.youtube.com/feeds/api/playlists/' + playlist_entry_id

        for i,v in enumerate(entries):
            video_id = get_video_id_from_url(v.url)
            if video_id:
                #
                # FIXME: the last two arguments seem to be ignored.
                #
                playlist_video_entry = self.yt.AddPlaylistVideoEntryToPlaylist(
                    playlist_uri, video_id, v.title, v.permalink)

                if isinstance(playlist_video_entry, 
                        gdata.youtube.YouTubePlaylistVideoEntry):
                    pass
                else:
                    self.error_queue.put(('Error saving playlist to YouTube', 
                        'Could not add video `%s\' to playlist' % video_id))
            else:
                print v.url, 'skipping'

            self.message_queue.put((None, float(i+1)/len(entries)))

            #
            # Respect the API call limits.
            #
            time.sleep(1)
        #
        # TODO: output a list of skipped entries.
        #

    def __check_completion(self):
        """Checks for completion of the worker thread periodically."""
        #
        # Time is in seconds in threading land.
        #
        try:
            title, message = self.error_queue.get(True, 0.1)
            tkMessageBox.showerror(title, message)
            self.progress.set(0)
            self.__enable_input(True)
            return
        except Queue.Empty:
            pass

        while True:
            try:
                message, progress = self.message_queue.get(True, 0.1)
                self.progress.set(progress,message)
            except Queue.Empty:
                break

        self.update_idletasks()

        if self.thread.isAlive():
            #
            # Time is in millis in Tkinter land.
            #
            self.after(10, self.__check_completion)
        else:
            self.__enable_input(True)

    def __enable_input(self, enable):
        """Disable/enable all interactive GUI widgets."""
        self.btn_start.configure(state=NORMAL if enable else DISABLED)

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
            '--config',
            '-c',
            dest='config',
            type='string',
            default='rvyt.cfg',
            help='Load the specified configuration file')
    return parser

def main():
    root = Tk()
    root.option_add('*tearOff', False)
    root.resizable(False, False)
    root.title('rvyt')
    #
    # FIXME: Not working on Linux for some reason.
    # 
    #root.iconbitmap('Reddit2.ico')

    parser = create_parser('usage: rvyt.exe [options]')
    options, args = parser.parse_args()
    if len(args) != 0:
        parser.error('invalid number of arguments')

    cfgparse = ConfigParser.SafeConfigParser()
    cfgparse.read(options.config)

    gui = RvytGUI(root, cfgparse)
    gui.pack()
    root.mainloop()

    try:
        root.destroy()
    except TclError:
        pass

if __name__ == '__main__':
    main()
