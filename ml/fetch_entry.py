"""
Fetch the details of a video entry and save it to a pickle.
The video ID is passed as a command-line arg.
"""

import gdata.youtube
import gdata.youtube.service
from gdata.service import RequestError
import pickle
KEY = 'AI39si7lnm9bcrVuwNa2p58l0KhqPvPgTKMm6K-Bi1ZzVaDNvqbiEvrZJZfFfpMvMhJfOyaDtIpqTcHu6Xrj5121B8aRXNI76A'

def get_details(vid):
    """
    Get title, author, publication time, description, tags, favorite count,
    view count, ratings, geo tag, and the time this query was made.
    """
    yt_service = gdata.youtube.service.YouTubeService()
    yt_service.developer_key = KEY
    entry = yt_service.GetYouTubeVideoEntry(video_id=vid)
    return entry

def create_parser():
    from optparse import OptionParser
    parser = OptionParser('usage: python %s video_id file.pickle [options]' % __file__)
    return parser
            
def main():
    parser = create_parser()
    options, args = parser.parse_args()
    if len(args) != 2:
        parser.error('insufficient arguments')

    try:
        details = get_details(args[0])
        fout = open(args[1], 'w')
        pickle.dump(details, fout)
        fout.close()
    except RequestError, re:
        print 'RequestError:', args[0], re[0]['body']

if __name__ == '__main__':
    main()
