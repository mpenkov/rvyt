import mako.lookup
import mako.exceptions
import os.path as P

import cherrypy

import orm
import satool

CURR_DIR = P.dirname(P.abspath(__file__))


class Root(object):
    _cp_config = {"tools.sessions.on": True}

    def __init__(self):
        self.lookup = mako.lookup.TemplateLookup(
            directories=["html"], default_filters=["decode.utf8"],
            input_encoding="utf-8", output_encoding="utf-8",
            strict_undefined=True)

    @cherrypy.expose
    def index(self, nsfw_filter="false", res="360"):
        submissions = cherrypy.request.db.query(orm.Submission).all()

        if nsfw_filter.lower() == "true":
            submissions = [s for s in submissions if s.is_safe()]

        try:
            height = int(res)
            width = int(height*16/9)
        except ValueError:
            width, height = 640, 360

        playlist = ",".join([sub.ytid for sub in submissions if sub.ytid])
        template = self.lookup.get_template("index.html")
        html = template.render(submissions=submissions, playlist=playlist,
                               width=width, height=height,
                               nsfw_filter=nsfw_filter)
        return html


def create_parser():
    from optparse import OptionParser
    parser = OptionParser(usage="%prog db.sqlite3 [options]")
    return parser


def main():
    parser = create_parser()
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("incorrect number of arguments")
    db_path = args[0]
    satool.SAEnginePlugin(cherrypy.engine, db_path).subscribe()
    cherrypy.tools.db = satool.SATool()

    config_file = P.join(CURR_DIR, "app.config")
    assert P.isfile(config_file)
    cherrypy.config.update(config_file)
    cherrypy.tree.mount(Root(), "", config=config_file)
    cherrypy.engine.start()
    cherrypy.engine.block()

if __name__ == "__main__":
    main()
