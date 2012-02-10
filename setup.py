from distutils.core import setup
import py2exe
setup(
    options = { 'py2exe' : { 'bundle_files' : 1 } },
    windows= [
        { 'script' : 'rvyt.py', 'icon_resources' : [(0, 'Reddit.ico')] } ], 
    data_files=['rvyt.cfg', 'reddit_api.cfg', 'Reddit2.ico' ],
    zipfile = None )
