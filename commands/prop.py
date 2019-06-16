""" prop.py

For propagating the database with wiki data.
"""

from helpers.api import wikidot_api_key
from helpers.error import CommandError
from xmlrpc.client import ServerProxy
from pprint import pprint
from helpers.parse import nickColor

def prop_print(text):
    print("[{}] {}".format(nickColor("Propagation"), text))

Server = ServerProxy('https://TARS:{}@www.wikidot.com/xml-rpc-api.php' \
                     .format(wikidot_api_key))

class propagate:
    @classmethod
    def command(cls, irc_c, msg, cmd):
        if msg.nick != "Croquembouche":
            raise CommandError("Only Croquembouche can do that.")
        # arg 1 should be a url name
        if len(cmd.args['root']) > 0:
            propagate.get_wiki_data_for(cmd.args['root'], reply = msg.reply)
        else:
            propagate.get_wiki_data(reply = msg.reply)

    @classmethod
    def get_wiki_data(cls, **kwargs):
        reply = kwargs.get('reply', lambda x: None)
        # 1. get a list of articles
        # 2. get data for each article
        # 2.5. put that data in the db
        prop_print("Getting list of pages...")
        pages = Server.pages.select({'site': "scp-wiki",
                                     'categories': ["_default"]})
        prop_print("Found {} pages".format(len(pages)))
        reply("Ding")

    @classmethod
    def get_wiki_data_for(cls, url, **kwargs):
        reply = kwargs.get('reply', lambda x: None)
        # get the wiki data for this article
        # we're taking all of root, so url is a list
        articles = Server.pages.get_meta({'site': "scp-wiki",
                                         'pages': url})
        for url,article in articles.items():
            reply(str(article))
            irc_c.db._driver.add_article(article)
