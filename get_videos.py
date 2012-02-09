"""Fetch some videos from r/videos and serialize them."""
import reddit
import pickle

USER_AGENT = 'https://github.com/mpenkov/rvyt'

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
            '--limit',
            '-l',
            dest='limit',
            type='int',
            default=10,
            help='Retrieve the top N videos')
    return parser

class Entry:
    """Serializable reddit.Submission."""
    def __init__(self, submission):
        for a in dir(submission):
            #
            # Don't worry about private attributes.  Also, some of the comment
            # attributes aren't friendly with getattr, so ignore them as well.
            #
            if a[0] == '_' or a.find('comments') != -1:
                continue
            v = getattr(submission, a)
            if type(v) in [ type(foo) for foo in [ 1, True, 'foo', u'foo' ] ]:
                setattr(self, a, v)

def main():
    parser = create_parser('usage: %s videos.pickle [options]' % __file__)
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error('invalid number of arguments')
    r = reddit.Reddit(user_agent=USER_AGENT)
    if options.user and options.passwd:
        r.login(options.user, options.passwd)
    entries = r.get_subreddit('videos').get_top(limit=options.limit)

    to_dump = []
    while True:
        try:
            to_dump.append(Entry(entries.next()))
        except StopIteration:
            break

    fout = open(args[0], 'w')
    pickle.dump(to_dump, fout)
    fout.close()

if __name__ == '__main__':
    import sys
    sys.exit(main())
