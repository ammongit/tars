"""converse.py

Responses for regular messages - ie, not commands.
Adding anything to this that doesn't refer directly to TARS is 100% a dick move
and should never be done.
"""

import re
import string

import commands
from commands.prop import chunks

from fuzzywuzzy import fuzz

from helpers.greetings import acronym, greet, greets
from helpers.database import DB
from helpers.config import CONFIG

class converse:
    @classmethod
    def command(cls, irc_c, msg, cmd):
        # Recieves text in msg.message
        message = cmd.unping

        ##### ping matches #####

        if cmd.pinged:
            if any(x in message.lower() for x in [
                "fuck you",
                "piss off",
                "fuck off",
            ]):
                msg.reply("{}: no u".format(msg.nick))
                return

        ##### ping-optional text matches #####

        if message.startswith("?? "):
            # CROM compatibility
            getattr(commands.COMMANDS, 'search').command(irc_c, msg, cmd)
        if message.lower() == "{}!".format(CONFIG.nick.lower()):
            msg.reply("{}!".format(msg.nick))
            return
        if strip(message.lower()) in [strip("{}{}".format(g,CONFIG.nick.lower()))
                                      for g in greets]:
            if msg.sender == 'XilasCrowe':
                msg.reply("toast")
                return
            msg.reply(greet(msg.nick))
            return
        if CONFIG.nick == "TARS" and matches_any_of(message, [
            "what does tars stand for?",
            "is tars an acronym?",
        ]) and "TARS" in message.upper():
            msg.reply(acronym())
            return
        if CONFIG.nick == "TARS" and matches_any_of(message, [
            "is tars a bot?",
            "tars are you a bot?",
        ]) and "TARS" in message.upper():
            msg.reply("Yep.")
            return
        if CONFIG.nick == "TARS" and matches_any_of(message, [
            "is tars a person?",
            "tars are you a person?",
        ]) and "TARS" in message.upper():
            msg.reply("Nope. I'm a bot.")
            return
        if CONFIG.nick == "TARS" and matches_any_of(message, [
            "what is your iq",
        ]) and "TARS" in message.upper():
            msg.reply("big")
            return

        ##### regex matches #####

        # give url for reddit links
        match = re.search(r"(?:^|\s)/?r/(\S*)", message, re.IGNORECASE)
        if match:
            msg.reply("https://www.reddit.com/r/{}".format(match.group(1)))
            return
        # tell me about new acronyms
        match = re.search(
            r"(\s+|(?:\s*[{0}]+\s*))".join(
                [r"([{{0}}]*)\b({})(\S*)\b([{{0}}]*)".format(l)
                 for l in CONFIG['IRC']['nick']])
            .format(re.escape(string.punctuation)),
            message, re.IGNORECASE | re.VERBOSE)
        if match:
            submatches = chunks(match.groups(), 5)
            msg.reply("".join(["{}\x02{}\x0F{}{}{}"
                               .format(*chunks(submatch, 5, ""))
                               for submatch in submatches]))

        ##### custom matches #####

        if (msg.sender == "Jazstar" and
            "slime" in msg.message and
            "XilasCrowe" in DB.get_channel_members(msg.raw_channel)):
            msg.reply("Oy xilas I heard you like slime!")
            return

        # after all attempts, must indicate failure if pinged
        if cmd.pinged:
            return 1

def strip(string):
    """Strips all non-alphanumeric characters."""
    return ''.join(l for l in string if l.isalnum()).lower()

def matches_any_of(subject, matches, threshold=80):
    for match in matches:
        if fuzz.ratio(subject.lower(), match) >= threshold:
            return True
    return False
