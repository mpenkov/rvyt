from Tkinter import *
import ImageTk
import tkMessageBox
import PIL.Image

import reddit
import pickle
import urllib2
import gdata.service

from ProgressMeter import Meter
from get_videos import RedditEntry, USER_AGENT
from save_playlist import save_playlist, DEFAULT_TITLE

class RvytGUI(Frame):
    def __init__(self, parent, initval):
        Frame.__init__(self, parent)
        self.remember = initval
        self.__create_widgets()
    def __create_widgets(self):
        pil = PIL.Image.open('rvideos.png')
        self.reddit_tk = ImageTk.PhotoImage(pil)
        lbl = Label(self, image=self.reddit_tk)
        lbl.grid(row=0,column=0,columnspan=2,sticky=W)
        
        lbl = Label(self, text='username:')
        lbl.grid(row=1,column=0,sticky=E)
        self.reddit_user = Entry(self)
        self.reddit_user.grid(row=1,column=1, sticky=(W,E))

        lbl = Label(self, text='password:')
        lbl.grid(row=2,column=0,sticky=E)
        self.reddit_passwd = Entry(self, show='*')
        self.reddit_passwd.grid(row=2,column=1, sticky=(W,E))

        self.rem_reddit = IntVar()
        self.chk_reddit = Checkbutton(self, text='remember',
                variable=self.rem_reddit)
        self.chk_reddit.grid(row=3,column=1,sticky=W)

        try:
            user,passwd = self.remember['reddit']
            self.reddit_user.insert(0,user)
            self.reddit_passwd.insert(0,passwd)
            self.rem_reddit.set(1)
        except KeyError:
            pass

        self.spinbox = Spinbox(self, values=(10,50,100))
        self.spinbox.grid(row=4,column=0,sticky=E)

        self.btn_fetch = Button(self, text='fetch', command=self.__fetch)
        self.btn_fetch.grid(row=4,column=1,sticky=E)

        pil = PIL.Image.open('youtube.png')
        self.youtube_tk = ImageTk.PhotoImage(pil)
        lbl = Label(self, image=self.youtube_tk)
        lbl.grid(row=5,column=0,columnspan=2,sticky=W)
        
        lbl = Label(self, text='username:')
        lbl.grid(row=6,column=0, sticky=E)
        self.youtube_user = Entry(self)
        self.youtube_user.grid(row=6,column=1, sticky=(W,E))

        lbl = Label(self, text='password:')
        lbl.grid(row=7,column=0, sticky=E)
        self.youtube_passwd = Entry(self, show='*')
        self.youtube_passwd.grid(row=7,column=1, sticky=(W,E))

        self.rem_youtube = IntVar()
        self.chk_youtube = Checkbutton(self, text='remember',
                variable=self.rem_youtube)
        self.chk_youtube.grid(row=8,column=1,sticky=W)

        try:
            user,passwd = self.remember['youtube']
            self.youtube_user.insert(0,user)
            self.youtube_passwd.insert(0,passwd)
            self.rem_youtube.set(1)
        except KeyError:
            pass

        self.btn_save = Button(self, text='save',command=self.__save)
        self.btn_save.grid(row=9,column=1,sticky=E)

        self.progress = Meter(self, relief='ridge', bd=3)
        self.progress.grid(row=10,column=0,columnspan=2)

    def __fetch(self):
        self.__enable_input(False)
        #
        # TODO: ideally this should be in a separate module but the code is so
        # trivial that it's simpler to just copy it across.
        #
        user = self.reddit_user.get()
        passwd = self.reddit_passwd.get()
        r = reddit.Reddit(user_agent=USER_AGENT)
        try:
            if user and passwd:
                #
                # FIXME: broken on Windows?
                # 
                r.login(user, passwd)
            limit = int(self.spinbox.get())
            entries = r.get_subreddit('videos').get_top(limit=limit)
            self.entries = []
            incr = 1.0/limit
            progress = 0
            while progress < 1.0:
                try:                
                    progress += incr
                    self.entries.append(RedditEntry(entries.next()))
                except StopIteration:
                    progress = 1.0
                self.progress.set(progress)
            self.progress.set(1.0, 'Fetched %d entries' % limit)

            fout = open('entries.pickle', 'w')
            pickle.dump(self.entries, fout)
            fout.close()

            if self.rem_reddit:
                self.remember['reddit'] = (user,passwd)
        except urllib2.URLError:
            tkMessageBox.showerror(
                    'Could not login', 'Check your login credentials')

        self.__enable_input(True)

    def __save(self):
        self.__enable_input(False)

        #
        # TODO: move this stuff to a separate thread.
        #

        user = self.youtube_user.get()
        passwd = self.youtube_passwd.get()
        self.entries = pickle.load(open('entries.pickle'))
        try:
            save_playlist(user,passwd,self.entries,DEFAULT_TITLE,self.__callback)
        except gdata.service.CaptchaRequired, cr:
            tkMessageBox.showerror(
                    'Could not login', 'Check your login credentials (%s)' % cr)

        if self.rem_youtube:
            self.remember['youtube'] = (user,passwd)

        self.__enable_input(True)

    def __callback(self, i, total):
        self.progress.set(float(i)/total)
        if i == total:
            self.progress.set(1.0, 'Saved %d entries' % i)

    def __enable_input(self, enable):
        for w in [ self.reddit_user, self.reddit_passwd, self.chk_reddit,
                   self.btn_fetch,
                   self.youtube_user, self.youtube_passwd, self.chk_youtube,
                   self.btn_save ]:
            w.configure(state=NORMAL if enable else DISABLED)

def main():
    root = Tk()
    root.option_add('*tearOff', False)
    root.resizable(False, False)
    root.title('rvyt')

    try:
        remember = pickle.load(open('remember.pickle'))
    except IOError:
        remember = {}

    gui = RvytGUI(root, remember)
    gui.pack()
    root.mainloop()

    try:
        root.destroy()
    except TclError:
        pass

    fout = open('remember.pickle', 'w')
    pickle.dump(gui.remember, fout)
    fout.close()

if __name__ == '__main__':
    main()
