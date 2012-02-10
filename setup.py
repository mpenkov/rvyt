from distutils.core import setup
import py2exe
setup(
    windows= [
        { 'script' : 'rvyt.py', 'icon_resources' : [(0, 'Reddit.ico')] } ], 
    data_files=['rvyt.cfg', 'reddit_api.cfg', 'Reddit2.ico' ])
