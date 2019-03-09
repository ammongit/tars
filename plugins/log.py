"""Log Plugin

Logs all input and output for recordkeeping purposes.
"""

import time
from pyaib.plugins import observe, plugin_class
from helpers import parse

@plugin_class('log')
class Log:
    def __init__(self, irc_c, config):
        print("Log Plugin Loaded!")

    @observe("IRC_MSG_PRIVMSG")
    def log(self, irc_c, msg):
        print("yeet")
        print("[{}] <{}> {}".format(
            time.strftime("%H:%M:%S"),
            parse.nickColor(msg.nick),
            msg.message
        ))