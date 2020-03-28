"""search.py

Search commands that search the wiki for stuff.
Commands:
    search - base command
    regexsearch - search with -x
    tags - search with root params lumped into -t
"""

from random import random

from commands._command import Command
from commands.gib import gib
from commands.showmore import showmore

from edtf import parse_edtf
from edtf.parser.edtf_exceptions import EDTFParseException
from fuzzywuzzy import fuzz
from googleapiclient.discovery import build
import pendulum as pd

from helpers.defer import defer
from helpers.api import google_api_key, cse_key
from helpers.error import CommandError, isint
from helpers.database import DB

try:
    import re2 as re
except ImportError:
    print("re2 failed to load, falling back to re")
    import re

class Search(Command):
    """Searches the wiki for pages.

    Provides URLs and basic info for the page(s) that match your search
    criteria. Searching is never case-sensitive."""
    command_name = "search"
    arguments = [
        [str, '*', "title",
         """Search for pages whose title contains all of these words.

         Words are space-separated. Like all commands, anything wrapped in
         quotemarks (``"``) will be treated as a single word. If you leave
         **title** empty, then it will match all pages, and you'll need to
         specify more criteria. If you actually need to search for quotemarks,
         escape them with a backslash - e.g. ``.s \\"The
         Administrator\\"``."""],
        [str, '*', "--regex", "-x",
         """Filter pages by a regular expression.

         You may use more than one regex in a single search, still delimited by
         a space. If you want to include a literal space in the regex, you
         should either wrap the whole regex in quotes or use ``\\s``
         instead."""],
        [str, '+', "--tags", "--tag", "--tagged", "-t",
         """Filter pages by tags.

         The matched pages must have all the tags that you specified, unless
         that tag starts with ``-``, in which case they must not have that
         tag."""],
        [str, '+', "--author", "--au", "--by", "-a",
         """Filter pages by exact author name.

         The matched pages must have all the authors that you specified, unless
         that author starts with ``-``, in which case they must not have that
         author."""],
        [str, '+', "--rating", "-r",
         """Filter pages by rating.

         Prefix the number with any of ``<``, ``>``, ``=``. Default is ``>``.
         Can also specify a range of ratings with two dots, e.g. ``20..50``.
         Ranges are always inclusive."""],
        [str, '+', "--created", "--date", "-c",
         """Filter pages by date of creation. Accepts both absolute and
         relative dates.

         Absolute dates must be in ISO-8601 format
         (YYYY-MM-DD, YYYY-MM or YYYY). Relative dates must be a number
         followed by a letter to specify how many units of time ago; valid
         units are ``s m h d w M y``. These units are not case-sensitive,
         **except for m/M!** Use ``m`` for minutes and ``M`` for Months.

         Can use the same prefixes as **rating** (``>`` = "older than",
         ``<`` = "younger than", ``=`` = exact match). ``=`` is the default
         prefix if not specified, though this is pretty much guaranteed to
         never match a relative date.

         Also supports ranges of dates with two dots e.g. ``2018..2019``.
         Ranges are always inclusive, and you can mix relative dates and
         absolute dates."""],
        [str, '+', "--category", "--cat", "-y"],
        [str, None, "--parent", "-p"],
        [bool, 0, "--summary", "--summarise", "-u"],
        [bool, 0, "--random", "--rand", "--ran", "-d"],
        [bool, 0, "--recommend", "--rec", "-m"],
        [bool, 0, "--newest", "--new", "-n"],
        [bool, 0, "--verbose", "-v"],
        [str, None, "--order", "-o"],
        [int, None, "--limit", "-l"],
        [int, None, "--offset", "-f"],
        ['hidden', bool, 0, "--ignorepromoted"]
    ]
    @classmethod
    def command(cls, irc_c, msg, cmd):
        # Check that we are actually able to do this
        # (might have to move to end for defer check)
        if (defer.check(cmd, 'jarvis', 'Secretary_Helen')):
            return
        # Parse the command itself
        cmd.expandargs(
            # --tags --tag --tagged -t  Filter by tags.
            # --author --au -a          Filter by authors.
            # --rating -r               Filter by rating.
            # --created --date -c       Filter by date.
            # --category --cat -y       Filter by category.
            # --parent -p               Filter by parent fullname.
            # --regex -x                Filter by regex match.
            # --summary --summarise -u  Return a summary of results.
            # --random --rand --ran -d  Return a random result.
            # --recommend --rec -m      Return a recommended result.
            # --newest --new -n         Return the newest result.
            # --verbose -v              Print search criteria.
            # --order -o                Order the results.
            # --limit -l                Limit the number of results.
            # --offset -f               Skip results from the start of the list.
            # --ignorepromoted          Ignore promoted articles.
            # """
            ["search",
        )
        # check to see if there are any arguments
        if len(cmd.args) == 1 and len(cmd.args['root']) == 0:
            raise CommandError("Must specify at least one search term")
        # fullname is deprecated for tars
        if 'fullname' in cmd:
            raise CommandError("TARS does not support fullname search - "
                               "wrap your search in quotemarks instead")
        # Set the return mode of the output
        selection = {
            'ignorepromoted': 'ignorepromoted' in cmd,
            'order': 'fuzzy',
            'limit': None,
            'offset': 0
        }
        # order, limit, offset
        if 'order' in cmd:
            if len(cmd['order']) != 1:
                raise CommandError("When using the order argument "
                                   "(--order/-o), exactly one order type must "
                                   "be specified")
            if cmd['order'][0] in ['recent', 'recommend', 'random', 'fuzzy', 'none']:
                if cmd['order'] == 'none':
                    selection['order'] = None
                else:
                    selection['order'] = cmd.args.order
            else:
                raise CommandError("Selection return order ('{}') must be "
                                   "one of: recent, recommend, random, "
                                   "fuzzy, none".format(cmd['order'][0]))
        if 'limit' in cmd:
            if len(cmd['limit']) != 1:
                raise CommandError("When using the limit argument "
                                   "(--limit/-l), exactly one limit must "
                                   "be specified")
            if isint(cmd['limit'][0]):
                if int(cmd['limit'][0]) > 0:
                    selection['limit'] = int(cmd['limit'][0])
                elif int(cmd['limit'][0]) == 0:
                    selection['limit'] = None
                else:
                    raise CommandError("When using the limit argument "
                                       "(--limit/-l), the limit must be at "
                                       "least 0")
            else:
                raise CommandError("When using the limit argument "
                                   "(--limit/-l), the limit must be an integer")
        if 'offset' in cmd:
            if len(cmd['offset']) != 1:
                raise CommandError("When using the offset argument "
                                   "(--offset/-f), exactly one offset must "
                                   "be specified")
            if isint(cmd['offset'][0]):
                if int(cmd['offset'][0]) >= 0:
                    selection['offset'] = int(cmd['offset'][0])
                else:
                    raise CommandError("When using the offset argument "
                                       "(--offset/-f), the offset must be at "
                                       "least 0")
            else:
                raise CommandError("When using the offset argument "
                                   "(--offset/-f), the offset must be an integer")
        if 'random' in cmd:
            selection['order'] = 'random'
            selection['limit'] = 1
        if 'recommend' in cmd:
            selection['order'] = 'recommend'
            selection['limit'] = 1
        if 'newest' in cmd:
            selection['order'] = 'recent'
            selection['limit'] = 1
        # What are we searching for?
        searches = []
        strings = []
        if len(cmd.args['root']) > 0:
            strings = cmd.args['root']
            searches.extend([{'term': s, 'type': None} for s in strings])
        # Add any regexes
        regexes = []
        if 'regex' in cmd:
            if len(cmd.args.regex) == 0:
                raise CommandError(
                    "When using the regular expression filter "
                    "(--regex/-x), at least one regex must "
                    "be specified"
                )
            for regex in cmd.args.regex:
                try:
                    re.compile(regex)
                except re.error as e:
                    raise CommandError(
                        "'{}' isn't a valid regular expression: {}"
                        .format(regex, e)
                    )
                regexes.append(regex)
                # don't append the compiled - SQL doesn't like that
            searches.extend([{'term': r, 'type': 'regex'} for r in regexes])
        # Set the tags
        tags = {'include': [], 'exclude': []}
        if 'tags' in cmd:
            if len(cmd.args.tags) == 0:
                raise CommandError(
                    "When using the tag filter (--tag/-t), at "
                    "least one tag must be specified"
                )
            for tag in cmd.args.tags:
                if tag[0] == "-":
                    tags['exclude'].append(tag[1:])
                    continue
                if tag[0] == "+":
                    tags['include'].append(tag[1:])
                    continue
                tags['include'].append(tag)
            searches.append({'term': tags, 'type': 'tags'})
        # Set the author
        authors = {'include': [], 'exclude': []}
        if 'author' in cmd:
            if len(cmd.args.author) == 0:
                raise CommandError(
                    "When using the author filter "
                    "(--author/-a), at least one author must "
                    "be specified"
                )
            for author in cmd.args.author:
                if author[0] == "-":
                    authors['exclude'].append(author[1:])
                    continue
                if author[0] == "+":
                    authors['include'].append(author[1:])
                    continue
                authors['include'].append(author)
            searches.append({'term': authors, 'type': 'author'})
        # Set the rating
        # Cases to account for: modifiers, range, combination
        ratings = MinMax()
        if 'rating' in cmd:
            if len(cmd.args.rating) == 0:
                raise CommandError(
                    "When using the rating filter "
                    "(--rating/-r), at least one rating must "
                    "be specified"
                )
            for rating in cmd.args.rating:
                if ".." in rating:
                    rating = rating.split("..")
                    if len(rating) > 2:
                        raise CommandError("Too many ratings in range")
                    try:
                        rating = [int(x) for x in rating]
                    except ValueError:
                        raise CommandError(
                            "Ratings in a range must be plain numbers"
                        )
                    try:
                        ratings >= min(rating)
                        ratings <= max(rating)
                    except MinMaxError as e:
                        raise CommandError(str(e).format("rating"))
                elif rating[0] in [">", "<", "="]:
                    pattern = r"^(?P<comp>[<>=]{1,2})(?P<value>[0-9]+)"
                    match = re.search(pattern, rating)
                    if match:
                        try:
                            rating = int(match.group('value'))
                        except ValueError:
                            raise CommandError("Invalid rating comparison")
                        comp = match.group('comp')
                        try:
                            if comp == ">=":
                                ratings >= rating
                            elif comp == "<=":
                                ratings <= rating
                            elif comp == "<":
                                ratings < rating
                            elif comp == ">":
                                ratings > rating
                            elif comp == "=":
                                ratings >= rating
                                ratings <= rating
                            else:
                                raise CommandError(
                                    "Unknown operator in rating comparison"
                                )
                        except MinMaxError as e:
                            raise CommandError(str(e).format("rating"))
                    else:
                        raise CommandError("Invalid rating comparison")
                else:
                    try:
                        rating = int(rating)
                    except ValueError:
                        raise CommandError(
                            "Rating must be a range, comparison, or number"
                        )
                    # Assume =, assign both
                    try:
                        ratings >= rating
                        ratings <= rating
                    except MinMaxError as e:
                        raise CommandError(str(e).format("rating"))
            searches.append({'term': ratings, 'type': 'rating'})
        # Set created date
        # Cases to handle: absolute, relative, range (which can be both)
        createds = MinMax()
        if 'created' in cmd:
            if len(cmd.args.created) == 0:
                raise CommandError(
                    "When using the date of creation filter "
                    "(--created/-c), at least one date must "
                    "be specified"
                )
            created = cmd.args.created
            # created is a list of date selectors - ranges, abs and rels
            # but ALL dates are ranges!
            created = [DateRange(c) for c in created]
            # created is now a list of DateRanges with min and max
            try:
                for selector in created:
                    if selector.max is not None:
                        createds <= selector.max
                    if selector.min is not None:
                        createds >= selector.min
            except MinMaxError as e:
                raise CommandError(str(e).format("date"))
            searches.append({'term': createds, 'type': 'date'})
        # Set category
        categories = {'include': [], 'exclude': []}
        if 'category' in cmd:
            if len(cmd.args.category) == 0:
                raise CommandError(
                    "When using the category filter "
                    "(--category/-y), at least one category "
                    "must be specified"
                )
            for category in cmd.args.category:
                if category[0] == "-":
                    categories['exclude'].append(category[1:])
                    continue
                if category[0] == "+":
                    categories['include'].append(category[1:])
                    continue
                categories['include'].append(category)
            searches.append({'term': categories, 'type': 'category'})
        # Set parent page
        parents = None
        if 'parent' in cmd:
            if len(cmd.args.parent) != 1:
                raise CommandError(
                    "When using the parent page filter "
                    "(--parent/-p), exactly one parent URL "
                    "must be specified"
                )
            parents = cmd.args.parent[0]
            searches.append({'term': parents, 'type': 'parent'})
        # FINAL BIT - summarise commands
        if 'verbose' in cmd:
            verbose = "Searching for articles "
            if len(strings) > 0:
                verbose += (
                    "containing \"{}\"; ".format("\", \"".join(strings))
                )
            if len(regexes) > 0:
                verbose += "matching the regex /{}/; ".format(
                    "/ & /".join(regexes)
                )
            if parents is not None:
                verbose += ("whose parent page is '{}'; ".format(parents))
            if len(categories['include']) == 1:
                verbose += (
                    "in the category '" + categories['include'][0] + "'; "
                )
            elif len(categories['include']) > 1:
                verbose += (
                    "in the categories '" + "', '".join(categories) + "; "
                )
            if len(categories['exclude']) == 1:
                verbose += (
                    "not in the category '" + categories['exclude'][0] + "'; "
                )
            elif len(categories['exclude']) > 1:
                verbose += (
                    "not in the categories '" + "', '".join(categories) + "; "
                )
            if len(tags['include']) > 0:
                verbose += (
                    "with the tags '" + "', '".join(tags['include']) + "'; "
                )
            if len(tags['exclude']) > 0:
                verbose += (
                    "without the tags '" + "', '".join(tags['exclude']) + "'; "
                )
            if len(authors['include']) > 0:
                verbose += ("by " + " & ".join(authors['include']) + "; ")
            if len(authors['exclude']) > 0:
                verbose += ("not by " + " or ".join(authors['exclude']) + "; ")
            if ratings['max'] is not None and ratings['min'] is not None:
                if ratings['max'] == ratings['min']:
                    verbose += (
                        "with a rating of " + str(ratings['max']) + "; "
                    )
                else:
                    verbose += (
                        "with a rating between " + str(ratings['min']) +
                        " and " + str(ratings['max']) + "; "
                    )
            elif ratings['max'] is not None:
                verbose += (
                    "with a rating less than " + str(ratings['max'] + 1) + "; "
                )
            elif ratings['min'] is not None:
                verbose += (
                    "with a rating greater than " + str(ratings['min'] - 1) +
                    "; "
                )
            if createds['min'] is not None and createds['max'] is not None:
                verbose += (
                    "created between " + createds['min'].to_datetime_string() +
                    " and " + createds['max'].to_datetime_string() + "; "
                )
            elif createds['max'] is not None:
                verbose += (
                    "created before " + createds['max'].to_datetime_string() +
                    "; "
                )
            elif createds['min'] is not None:
                verbose += (
                    "created after " + createds['min'].to_datetime_string() +
                    "; "
                )
            if verbose.endswith("; "):
                verbose = verbose[:-2]
            msg.reply(verbose)

        page_ids = DB.get_articles(searches)
        pages = [DB.get_article_info(p_id) for p_id in page_ids]
        pages = search.order(pages, search_term=strings, **selection)

        if len(pages) >= 50:
            msg.reply("{} results found - you're going to have to be more "
                      "specific!".format(len(pages)))
            return
        if len(pages) > 3:
            msg.reply("{} results (use ..sm to choose): {}".format(
                len(pages), showmore.parse_multiple_titles(pages)))
            DB.set_showmore_list(msg.raw_channel, [p['id'] for p in pages])
            return
        if len(pages) == 0:
            # check if there's no args other than --verbose
            if set(cmd.args).issubset({'root', 'verbose'}):
                # google only takes 10 args
                url = google_search(
                    '"' + '" "'.join(cmd.args['root'][:10]) + '"', num=1
                )[0]
                if url is None:
                    msg.reply("No matches found.")
                    return
                if url['title'].endswith(" - SCP Foundation"):
                    url['title'] = url['title'][:-17]
                msg.reply(
                    "No matches found. Did you mean \x02{}\x0F? {}"
                    .format(url['title'], url['link'])
                )
            else:
                msg.reply("No matches found.")
            return
        for page in pages:
            msg.reply(gib.obfuscate(showmore.parse_title(page),
                                    DB.get_channel_members(msg.raw_channel)))

    @staticmethod
    def order(pages, search_term=None,
              order=None, limit=None, offset=0, **wanted_filters):
        """Order the results of a search by `order`.
        If `order` is None, then order by fuzzywuzzy of the search term.
        `search_term` should be a list of strings.
        """
        # filters should only be {'ignorepromoted':False} atm
        filters = {
            'ignorepromoted': lambda page: not page['is_promoted'],
        }
        orders = {
            'random': lambda page: random(),
            'recent': lambda page: -page['date_posted'],
            'fuzzy': lambda page: -sum([fuzz.ratio(s, page['title'])
                                        for s in search_term]),
            # 'recommend': None,
        }
        for wanted_filter, wanted in wanted_filters.items():
            if not wanted:
                continue
            pages = filter(filters[wanted_filter], pages)
        if order is not None:
            pages = sorted(pages, key=orders[order])
        pages = pages[offset:]
        pages = pages[:limit]
        return pages

class regexsearch:
    @classmethod
    def command(cls, irc_c, msg, cmd):
        cmd.args['regex'] = cmd.args['root']
        cmd.args['root'] = []
        search.command(irc_c, msg, cmd)

class tags:
    @classmethod
    def command(cls, irc_c, msg, cmd):
        cmd.args['tags'] = cmd.args['root']
        cmd.args['root'] = []
        search.command(irc_c, msg, cmd)

class lastcreated:
    @classmethod
    def command(cls, irc_c, msg, cmd):
        cmd.args['order'] = ['recent']
        if len(cmd.args['root']) > 0:
            cmd.args['limit'] = cmd.args['root']
            cmd.args['root'] = []
        else:
            cmd.args['limit'] = [3]
        # to make the query faster, if there's no other arguments, limit date
        # the minimum args are root, order, limit and optionally verbose
        # must expandargs to convert v to verbose
        search.expandargs(cmd)
        if set(cmd.args).issubset({'root', 'order', 'limit', 'verbose'}):
            cmd.args['created'] = ["<3d"]
        search.command(irc_c, msg, cmd)

class MinMax:
    """Stores a minimum int and a maximum int representing a range of values,
    inclusive.
    Once set, values are immutable.
    """
    def __repr__(self):
        return "MinMax({}..{})".format(self.min, self.max)

    def __init__(self, min_value=None, max_value=None):
        if max_value is not None and not isinstance(max_value, int):
            raise TypeError("Max must be int or None ({})".format(max_value))
        if min_value is not None and not isinstance(min_value, int):
            raise TypeError("Min must be int or None ({})".format(min_value))
        self.min = min_value
        self.max = min_value

    def __lt__(self, other):  # MinMax < 20
        if self.max is None:
            if self.min is not None and self.min > other:
                MinMax.throw('discrep')
            else:
                self.max = other - 1
        else:
            MinMax.throw('max')

    def __gt__(self, other):  # MinMax > 20
        if self.min is None:
            if self.max is not None and self.max < other:
                MinMax.throw('discrep')
            else:
                self.min = other + 1
        else:
            MinMax.throw('min')

    def __le__(self, other):  # MinMax <= 20
        if self.max is None:
            if self.min is not None and self.min > other:
                MinMax.throw('discrep')
            else:
                self.max = other
        else:
            MinMax.throw('max')

    def __ge__(self, other):  # MinMax <= 20
        if self.min is None:
            if self.max is not None and self.max < other:
                MinMax.throw('discrep')
            else:
                self.min = other
        else:
            MinMax.throw('min')

    def __getitem__(self, arg):  # MinMax['min']
        if arg == 'min':
            return self.min
        if arg == 'max':
            return self.max
        raise KeyError(arg + " not in a MinMax object")

    @staticmethod
    def throw(type):
        if type == 'discrep':
            raise MinMaxError("Minimum {0} cannot be greater than maximum {0}")
        if type == 'min':
            raise MinMaxError("Can only have one minimum {0}")
        if type == 'max':
            raise MinMaxError("Can only have one maximum {0}")
        raise ValueError("Unknown MinMaxError {}".format(type))

class MinMaxError(Exception):
    pass

class DateRange:
    """A non-precise date for creating date ranges"""
    def __repr__(self):
        return "DateRange({}..{})".format(self.min, self.max)

    # Each DateRange should have 2 datetimes:
    # 1. when it starts
    # 2. when it ends
    # Then when we make a range with the date, we take the one that gives the
    # largest range
    # Takes BOTH explicit ranges and implicit dates
    datestr = "{}-{}-{} {}:{}:{}"

    def __init__(self, input_date):
        self.input = input_date
        self.min = None
        self.max = None
        self.compare = None
        # possible values:
        # 1. absolute date
        # 2. relative date
        # 3. range (relative or absolute)
        # for absolute:
        # parse
        # create max and min
        # for relative:
        # create a timedelta
        # subtract that from now
        # no need for max and min, subtraction is precise
        # for range:
        # create a DateRange for each
        # select max and min from both to create largest possible range
        # first let's handle the range
        if ".." in self.input:
            self.input = self.input.split("..")
            if len(self.input) != 2:
                raise CommandError("Date ranges must have 2 dates")
            # if the date is a manual range, convert to a DateRange
            self.max = []
            self.min = []
            for date in self.input:
                date = DateRange(date)
                self.max.append(date.max)
                self.min.append(date.min)
            # max and min are now both lists of possible dates
            # pick max and min to yield the biggest date
            # max: None is always Now
            # min: None is alwyas The Beginning of Time
            # for 2 absolute dates this is easy, just pick biggest diff
            # for 2 relative dates, pick both of whichever is not None
            # for 1:1, pick not None of relative then ->largest of absolute
            # filter None from lists
            self.max = [i for i in self.max if i]
            self.min = [i for i in self.min if i]
            # special case for 2 relative dates - both will only have max
            if len(self.max) == 2 and len(self.min) == 0:
                self.min = min(self.max)
                self.max = max(self.max)
                return
            diffs = []
            for i, minimum in enumerate(self.min):
                for j, maximum in enumerate(self.max):
                    diffs.append({
                        'i': i,
                        'j': j,
                        'diff': self.min[i].diff(self.max[j]).in_seconds()
                    })
            diffs = max(diffs, key=lambda x: x['diff'])
            self.max = self.max[diffs['j']]
            self.min = self.min[diffs['i']]
            # do other stuff
            return
        # strip the comparison
        match = re.match(r"([>=<]{1,2})(.*)", self.input)
        if match:
            self.compare = match.group(1)
            self.input = match.group(2)
        if self.date_is_absolute():
            # the date is absolute
            # minimise the date
            self.min = pd.datetime(*self.date.lower_strict()[:6])
            self.min = self.min.set(hour=0, minute=0, second=0)
            # maximise the date
            self.max = pd.datetime(*self.date.upper_strict()[:6])
            self.max = self.max.set(hour=23, minute=59, second=59)
            pass
        elif re.match(r"([0-9]+[A-Za-z])+$", self.input):
            # the date is relative
            sel = [i for i in re.split(r"([0-9]+)", self.input) if i]
            # sel is now a number-letter-repeat list
            # convert list to dict via pairwise
            sel = DateRange.reverse_pairwise(sel)
            # convert all numbers to int
            sel = dict([a, int(x)] for a, x in sel.items())
            self.date = pd.now()
            # check time units
            for key in sel:
                if key not in 'smhdwMy':
                    raise CommandError(
                        "'{}' isn't a valid unit of time in a relative date. "
                        "Valid units are s, m, h, d, w, M, and y."
                        .format(key)
                    )
            self.date = pd.now().subtract(
                years=sel.get('y', 0),
                months=sel.get('M', 0),
                weeks=sel.get('w', 0),
                days=sel.get('d', 0),
                hours=sel.get('h', 0),
                minutes=sel.get('m', 0),
                seconds=sel.get('s', 0),
            )
            if self.compare in ["<", "<="]:
                self.min = self.date
            elif self.compare in [">", ">="] or self.compare is None:
                self.max = self.date
            elif self.compare == "=":
                self.max = self.date
                self.min = self.date
                # possible broken - may match to the second
            else:
                raise CommandError(
                    "Unknown operator in relative date "
                    "comparison ({})".format(self.compare)
                )
        else:
            raise CommandError(
                "'{}' isn't a valid absolute or relative date "
                "type".format(self.input)
            )

    def date_is_absolute(self):
        try:
            self.date = parse_edtf(self.input)
        except EDTFParseException:
            try:
                pd.parse(self.input)
            except pd.parsing.exceptions.ParserError:
                return False
            else:
                raise CommandError("Absolute dates must be of the format "
                                   "YYYY, YYYY-MM or YYYY-MM-DD")
        else:
            return True

    @staticmethod
    def reverse_pairwise(iterable):
        return dict(zip(*[iter(reversed(iterable))] * 2))

    def __getitem__(self, arg):  # MinMax['min']
        if arg is 'min':
            return self.min
        elif arg is 'max':
            return self.max
        else:
            raise KeyError(arg + " not in a DateRange object")


# TODO move this to helpers/api.py
def google_search(search_term, **kwargs):
    """Performs a mismatch search via google"""
    service = build("customsearch", "v1", developerKey=google_api_key)
    res = service.cse().list(q=search_term, cx=cse_key, **kwargs).execute()
    if 'items' in res:
        return res['items']
    return [None]
