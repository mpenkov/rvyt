import datetime
import re

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

SHORT_TITLE_LEN = 40


Base = declarative_base()


def extract_id(url):
    """Extract a YouTube ID from a URL."""
    #
    # YouTube attribution links.
    # More info:
    # http://techcrunch.com/2011/06/01/youtube-now-lets-you-license-videos-under-creative-commons-remixers-rejoice/
    # Example:
    # http://www.youtube.com/attribution_link?a=P3m5pZfhr5Y&u=%2Fwatch%3Fv%3DHnc-1rXLx_4%26feature%3Dshare
    m = re.search("watch%3Fv%3D(?P<id>[a-zA-Z0-9-_]{11})", url)
    if m:
        return m.group("id")

    #
    # Regular YouTube links.
    #
    m = re.search(r"youtu\.?be.*(v=|/)(?P<id>[a-zA-Z0-9-_]{11})", url)
    if m:
        return m.group("id")
    return None


class Submission(Base):
    __tablename__ = "submissions"

    rank = Column(Integer, primary_key=True)
    permalink = Column(String)
    url = Column(String)
    ytid = Column(String)
    title = Column(String)
    score = Column(Integer)
    timestamp = Column(DateTime)

    def __init__(self, sub, rank):
        self.rank = rank
        self.permalink = sub.permalink
        self.url = sub.url
        self.ytid = extract_id(sub.url)
        self.title = sub.title
        self.score = sub.score
        self.timestamp = datetime.datetime.now()

    def safe_title(self):
        return self.title.replace('"', "'")

    def short_title(self):
        if len(self.title) >= SHORT_TITLE_LEN:
            return self.title[:SHORT_TITLE_LEN] + "..."
        return self.title

    def is_safe(self):
        title = self.title.lower()
        return title.find("nsfw") == -1 and title.find("nsfl") == -1
