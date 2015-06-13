import sqlalchemy
import sqlalchemy.orm
import logging
logger = logging.getLogger(__name__)

import praw

import orm

USER_AGENT = "/u/mishapenkov (https://github.com/mpenkov/rvyt)"

LIMIT = 100


def update(session):
    meth_name = "update"

    r = praw.Reddit(USER_AGENT)
    session.query(orm.Submission).delete()

    for i, sub in enumerate(r.get_subreddit("videos").get_top(limit=LIMIT)):
        submission = orm.Submission(sub, i)
        if submission.ytid is None:
            logger.debug("%s: skipping submission URL: %s", meth_name, sub.url)
            continue
        session.add(submission)


def main():
    from optparse import OptionParser
    parser = OptionParser(usage="%prog file.sqlite3 [options]")
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("incorrect number of arguments")

    dbfilepath = args[0]
    engine = sqlalchemy.create_engine("sqlite:///" + dbfilepath, echo=False)
    orm.Base.metadata.create_all(engine)
    Session = sqlalchemy.orm.sessionmaker(bind=engine)
    session = Session()

    update(session)

    session.commit()

if __name__ == "__main__":
    main()
