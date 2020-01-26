# Not a plugin
# Provides generic text for shit

from random import choice
import re
from helpers.config import CONFIG

greets = [
    "Hey",
    "Howdy",
    "Hi",
    "Hello",
]
def greet(subject):
    channel = [
        "Hey everyone.",
        "Great, looks like everyone's already here.",
        "You guys... started without me?",
        "This is my new favourite channel.",
        "This is my new least favourite channel.",
    ]
    if subject[0] == "#":
        return choice(channel).format(subject)
    else:
        if subject == "Croquembouche":
            return "👉😎👉"
        else:
            return "{}, {}.".format(choice(greets), subject)

def bad_command(**kwargs):
    response = [
        "I'm sorry, I didn't quite catch that.",
        "That's not a valid command.",
        "I don't know how to do that.",
        "Are you sure you typed the right thing?",
        "I don't know what that means.",
        "That's not a command.",
        "Bad command, sorry.",
    ]
    message = kwargs['message'] if 'message' in kwargs else choice(response)
    link = " See https://git.io/TARShelp for a list of commands."
    return message + link

def isGreeting(message):
    greetings = [
        "hello", "hi", "howdy", "yo"
    ]
    return 0

def kill_bye():
    responses = [
        "Ok :(",
        "I don't wanna go :(",
        "Finally.",
    ]
    return choice(responses)

def acronym_gen():
    responses = [
        "!Tool-!Assisted !Robotic !Sassmouth",
        "!TARS: !A !Recursive !Semantic",
        "!Totally !Awesome !Robot (/!S)",
        "!Tantalising !And !Rambunctious !Sexbot",
        "ano!Ther bot that !Also helps io do p!Romotion !Stuff",
        "!Target !Attack !Radar !System",
        "!This's !A !Random !Sentence",
        "!Tell !Aaron !Rocks !Suck",
        "!There's !A !Rong !Spelling",
        "!This !Asshole !Robot !Sucks",
        "!Try !And !Rate !SCPs",
        "!These !Acronyms !Really !Suck",
        "I stand for robot rights.",
        "!Top !And !Rear !Suggested",
        "!Tales !Are !Real !Shit",
        "!TARS' !Ass? !Real !Soft.",
        "It's just SRAT but backwards.",
        "!Tummy & !Ass !Rubs, !Sergeant",
        "!Thanks, !Anderson !Robotics. !Sweet.",
        "!Trying !Acronyms !Repeatedly? !Super!",
        "!Tried !Adding !Rounderhouse - !Sorry!",
        "!That's !A !Regretful !Sentence",
        "!These !Are !Really !Something.",
        "!TARS !Acronym !Repeating !Successfully",
        "!Turnt !At #!Romanticpenthouse!Suite",
        "!T!A!R!SPWTCOTTTADC",
        "!Total !Anal !Relapse !Surgery",
        "!Two !Anuses !Rigorously !Spread",
    ]
    last_response = []
    while True:
        response = choice(responses)
        if response not in last_response:
            yield re.sub(r"!([TARS])", "\x02\\1\x0F", response)
            last_response.insert(0, response)
            last_response = last_response[:5]
acro = acronym_gen()
def acronym():
    if CONFIG.nick == "CASE":
        return "Croquembouche's Alt Sucks Extremely"
    elif CONFIG.nick == "TARS":
        return next(acro)
    else:
        return "It doesn't really stand for anything"
