"""Create an empty DB for the application."""
import os.path as P
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import orm


def main():
    from optparse import OptionParser
    parser = OptionParser(usage="%prog file.sqlite3 [options]")
    parser.add_option("-f", "--force", dest="force", default=False,
                      action="store_true", help="Overwrite existing file")
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("incorrect number of arguments")

    dbfilepath = args[0]

    if P.isfile(dbfilepath):
        if options.force:
            os.remove(dbfilepath)
        else:
            parser.error("file already exists")

    engine = create_engine("sqlite:///" + dbfilepath, echo=False)
    orm.Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()
    session.commit()

if __name__ == "__main__":
    main()
