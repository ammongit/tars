""" config.py

Parses the config file. Totally separate to pyaib's implementation, I promise
Exports CONFIG, equal to irc_c.config (probably)
"""

import sys
import yaml
from pprint import pprint

argv = sys.argv[1:]
configfile = argv[0] if argv else 'tars.conf'

with open(configfile, 'r') as file:
    CONFIG = yaml.safe_load(file)
    CONFIG['nick'] = CONFIG['IRC']['nick'] # might save me a few keystrokes
    print("Loaded {} to secondary config access".format(configfile))
