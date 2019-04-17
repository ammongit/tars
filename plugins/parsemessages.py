"""parsemessages

Plugin that parses messages into commands and then does stuff
"""

from helpers import parse
from commands import COMMANDS
from pyaib.plugins import observe, plugin_class
import sys
import inspect
from helpers.error import CommandError

@plugin_class("parsemessages")
class ParseMessages(object):
    def __init__(self, irc_c, config):
        print("Parse plugin loaded!")
        # The config is conf's plugin.parse
        # TODO generate COMMANDS from commands folder
        self.COMMANDS = {}
        # for cmd_group in commands:
        # do we really need this?
        # could just attempt the command and if it fails assume that the
        # command doesn't exist

    @observe("IRC_MSG_PRIVMSG")
    def handleMessage(self, irc_c, msg):
        cmd = parse.command(msg.message)
        # cmd is the parsed msg (used to be msg.parsed)
        if cmd.command:
            # this is a command!
            try:
                # Call the command from the right file in commands/
                # getattr instead of commands[cmd] bc module subscriptability
                getattr(COMMANDS, cmd.command).command(irc_c, msg, cmd)
            except AttributeError as e:
                # if specific attr error, command doesn't exist
                if "'Commands_Directory' object has no attribute" in str(e):
                    msg.reply("That's not a command.")
                else:
                    msg.reply("An unexpected error has occurred.")
                    raise
            except CommandError as e:
                msg.reply("Invalid command: {}".format(str(e)))
            except:
                msg.reply("An unexpected error has occurred.")
                raise
        elif cmd.pinged:
            # this isn't a command, but we were pinged
            # notify the user that it's a bad command IF not a greeting
            if msg.message.lower() == "tars!":
                msg.reply("{}!".format(msg.nick))
        else:
            # not a command, and not pinged
            pass
        if msg.channel is None:
            # we're working in PMs
            pass
        else:
            # we're in a channel
            pass
