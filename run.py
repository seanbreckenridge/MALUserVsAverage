import sys
import argparse
from json import load, dumps
from json.decoder import JSONDecodeError
from re import match
from os import path
from csv import writer
from time import time
from itertools import chain

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnchoredText
from scipy import stats

from manual_crawler import crawl
import jikanwrapper

JSON_FILENAME = "anime_cache.json"
# global representing we're scraping anime/manga
_type = jikanwrapper.Jikan.ANIME


def scrape_type():
    """Helper function to return anime/manga to be inserted into URLs"""
    if _type:
        return "anime"
    else:
        return "manga"


def current_unix_time():
    return time()


def has_passed_time_difference(oldtime, difference_in_days):
    """
        args:
            oldtime: unix time of old scrape
            difference_in_days: allowed cache time
        returns:
            True if we need to scrape again; values in cache have been there too long."""
    return time() > float(oldtime) + float(difference_in_days * 60 * 60 * 24)


def rudimentary_scraper(scraper, id):
    """Uses bs4 to scrape the score from MAL directly"""
    score = scraper.get_soup(url="https://myanimelist.net/{}/{}".format(
            scrape_type(), id)).find("div", {"data-title": "score"}).text.strip()
    if score == "N/A":
        score = 0
    return float(score)


def get_status(status_td):
    """Takes a td as input and returns the relevant status"""
    if 'status-P' in status_td["class"]:
        status = "Plan to Watch"
    elif 'status-F' in status_td["class"]:
        status = "Completed"
    elif 'status-D' in status_td["class"]:
        status = "Dropped"
    elif 'status-H' in status_td["class"]:
        status = "On-Hold"
    elif 'status-C' in status_td["class"]:
        status = "Currently Watching"
    else:
        status = None
    return status


def update_json_file(json_fullpath, all_items):
    """Overwrites the JSON file with any new data"""
    with open(json_fullpath, 'w') as js_f:
        js_f.write(dumps(all_items))


class fixFormatter(argparse.HelpFormatter):
    """Class to allow multi line help statements in argparse"""
    def _split_lines(self, text, width):
        if text.startswith('M|'):  # multiline statement
            return text[2:].splitlines()
        # this is the RawTextHelpFormatter._split_lines
        return argparse.HelpFormatter._split_lines(self, text, width)


class UnknownUser(Exception):
    """User could not be found on graph.anime.plus"""
    pass


class CacheError(Exception):
    pass


class Cache:
    """Class that caches requests to local json file, and scrapes for scores that could not be found."""
    def __init__(self, time_diff, jikan, scraper):
        print("Fixing cache...")
        self.write_to_cache_periodically = 25
        self.allowed_time_diff = time_diff
        self.jikan = jikan
        self.scraper = scraper
        self.json_fullpath = path.join(path.dirname(path.realpath(__file__)), JSON_FILENAME)
        if not path.exists(self.json_fullpath):
            open(self.json_fullpath, 'a').close()
        with open(self.json_fullpath, 'r') as js_f:
            try:
                self.items = load(js_f)
            except JSONDecodeError:  # file is empty or broken
                self.items = {}
        self.update_runtime_cache()

    def update_runtime_cache(self):
        """When cache is initialized, update any cache items that may be out of date.
        Doesn't have to be run, """
        for mal_id in list(self.items):
            if self.not_valid_cache_item(mal_id):
                print(f"Outdated score for {mal_id} in cache, updating", end=" ")
                score = self.download_score(id=mal_id, log_protocol=True)
                print(score)
                self.items[str(mal_id)] = {"unix": str(current_unix_time()), "score": str(score)}

    def download_score(self, id, log_protocol):
        """Download a score from MAL. Uses Jikan API if possible, else manually scrapes."""
        try:
            score = self.jikan.get_score(id, _type)
            if log_protocol:
                print("[Jikan]", end=": ")
        except jikanwrapper.JikanException:
            score = rudimentary_scraper(self.scraper, id)
            if log_protocol:
                print("[MAL]", end=": ")
        # update the cache every so often incase we crash
        self.write_to_cache_periodically -= 1
        if self.write_to_cache_periodically < 0:
            self.write_to_cache_periodically = 50
            update_json_file(self.json_fullpath, self.items)
        return score

    def __contains__(self, item):
        """defines the 'in' keyword on cache."""
        return str(item) in self.items

    def not_valid_cache_item(self, mal_id):
        """If it is still within the allowed time frame."""
        return has_passed_time_difference(self.items[str(mal_id)]["unix"], self.allowed_time_diff) or float(self.items[str(mal_id)]["score"]) == 0.0

    def get(self, id):
        """Gets the score for the id from cache if it exists, else raises a CacheError"""
        if self.__contains__(id):
            if self.not_valid_cache_item(id):
                raise CacheError("Item not within allowed time frame.")
            return self.items[str(id)]["score"]
        else:
            raise CacheError("That item isn't in the cache.")

    def put(self, id, score):
        """Puts an item into cache; updates the unix time"""
        self.items[str(id)] = {"unix": str(current_unix_time()), "score": str(score)}


class list_item:

    def __init__(self, tr, cache):

        status_td, title_td, user_score_td, diff_score_td = tr.find_all("td")

        # name
        self.name = title_td.find("a").text

        # mal link
        self.mal_url = title_td.find("a")["href"]

        # mal id
        self.mal_id = match(f"https:\/\/myanimelist\.net\/{scrape_type()}\/(\d+)", self.mal_url).groups(1)[0]

        # status
        self.status = get_status(status_td)

        # user rating
        self.user_rating = float(user_score_td.text)

        # difference
        diff_text = diff_score_td.find("span").text
        sign, score_value = diff_text[0], diff_text[1:]
        # split +3.00 into '+' and '3.00'
        if sign == "+":
            self.diff = float(score_value)
        elif sign == "-":
            self.diff = float(score_value) * -1
        else:  # i.e. diff is 0.00, neither '+' or '-'
            self.diff = float(0)

        # mal score
        if self.diff == self.user_rating:  # need to check if diff is correct, and its not that there aren't enough scores on MAL
            print(f"MAL has under 50 ratings, score for {self.mal_id} not listed on graph.anime.plus.", end=" ")
            try:
                score = cache.get(self.mal_id)
                print(f"Found score in cache: {score}")
            except CacheError:
                print(f"Downloading score", end=" ")
                score = cache.download_score(id=self.mal_id, log_protocol=True)
                print(score)
                cache.put(self.mal_id, score)
        else:
            cache.put(self.mal_id, self.user_rating - self.diff)

        self.mal_average_rating = cache.get(self.mal_id)

    def __str__(self):
        return f"""Name: {self.name}
MAL Link: {self.mal_url}
MAL ID: {self.mal_id}
User Rating: {self.user_rating}
MAL Score: {self.mal_average_rating}
Difference: {self.diff}
Status: {self.status}"""

    def __repr__(self):
        return __str__()


def options():
    global JSON_FILENAME
    global _type

    status_map = {"W": "Currently Watching", "C": "Completed", "O": "On-Hold", "D": "Dropped", "P": "Plan to Watch"}

    parser = argparse.ArgumentParser(description="Create user vs average MAL Score correlation graphs.", prog="python3 {}".format(sys.argv[0]), formatter_class=lambda prog: fixFormatter(prog, max_help_position=40))
    optionals = parser._action_groups.pop()
    required = parser.add_argument_group('required arguemnts')
    required.add_argument("-u", "--username", help="The MAL User for who the list/graph should be generated.", required=True)
    scrape_type = required.add_mutually_exclusive_group(required=True)
    scrape_type.add_argument("-a", "--anime", help="Create a graph/csv file for this users anime.", action="store_true")
    scrape_type.add_argument("-m", "--manga", help="Create a graph/csv file for this users manga.", action="store_true")
    optionals.add_argument("--cache-decay-time", type=int, help="Number of days scores should stay in cache before they are refresed. If not provided, uses 2 weeks.")
    optionals.add_argument("-w", "--wait-time", type=int, help="Wait time between (manual; non-API) scrape requests. Default and recomended is 5 (seconds).")
    optionals.add_argument("-f", "--filter", help="M|Filter by Status,\ne.g. '-f WC' would filter so output\ncontained only Watching and Completed.\n" +
                           "W: Currently Watching\n" +
                           "C: Completed\n" +
                           "O: On-Hold\n" +
                           "D: Dropped\n" +
                           "P: Plan to Watch\n"
                           )
    parser._action_groups.append(optionals)
    choose_outputs = parser.add_argument_group("(optional) output options (Generates both if nothing specified)")
    choose_outputs.add_argument("-c", "--csv", help="Output a CSV File.", action="store_true")
    choose_outputs.add_argument("-g", "--graph", help="Output a graph.", action="store_true")
    choose_outputs.add_argument("-d", "--display-name", help="Display the username on the graph.", action="store_true")
    args = parser.parse_args()

    if args.wait_time is None:
        args.wait_time = 5
    elif args.wait_time < 2:
        raise RuntimeError("Wait time should be more than 2.")
    else:
        args.wait_time = int(args.wait_time)

    if args.cache_decay_time is None:
        args.cache_decay_time = 14
    else:
        args.cache_decay_time = int(args.cache_decay_time)

    if args.filter is None or args.filter.strip() == "":
        status_list = [status_map[c] for c in "WCODP"]
    else:
        status_list = [status_map[c] for c in args.filter]

    if args.manga:
        _type = jikanwrapper.Jikan.MANGA
        JSON_FILENAME = "manga_cache.json"

    # If neither was mentioned, do both; else, only do the one mentioned in args
    if not args.csv and not args.graph:
        args.csv, args.graph = True, True

    # username, wait time, reset cache, csv, graph
    return args.username, args.wait_time, args.cache_decay_time, args.display_name, status_list, args.csv, args.graph


def make_graph(x, y, output_name, username, display_name):

    # Make scatter plot
    x = np.array(x)
    y = np.array(y)

    # regression
    slope, intercept, r_val, p_val, std_err = stats.linregress(x, y)
    # print(f"{username},{slope},{intercept},{r_val},{p_val},{std_err}")
    r_squared = r_val ** 2
    regression_y = intercept + slope * x

    # make plot rectangle
    plt.figure(figsize=(12, 6))
    # scatter plot
    plt.scatter(x, y, color='blue', marker='|')
    # regression line
    plt.plot(x, regression_y, color='black', linestyle='solid')

    # Title if wanted
    if not display_name:
        plt.title(f'[{scrape_type().capitalize()}] User to Consensus Score Correlation')
    else:
        plt.title(f'{username} - [{scrape_type().capitalize()}] User to Consensus Score Correlation')

    # label axes
    plt.xlabel('Average MAL Score')
    plt.ylabel('User Score')

    # no grid
    plt.grid(False)

    # add tick for each score
    plt.xticks(np.arange(1, 11, 1))
    plt.yticks(np.arange(1, 11, 1))

    # annotate r^2 value onto the graph
    plt.annotate('r²: {}'.format(r_squared), xy=(0.05, 0.95), xycoords='axes fraction')

    # plt.show()
    plt.savefig(f"{output_name}.png")


def get_graph_anime_trs(username, scraper):
    print("Downloading graph.anime.plus page...")
    url = "https://graph.anime.plus/{}/list,{}".format(username, scrape_type())
    graph_anime_page = scraper.get_soup(url)
    graph_anime_page_title = graph_anime_page.find("h2")
    if graph_anime_page_title and graph_anime_page_title.text.strip().lower() == "user not found":
        raise UnknownUser("""Couldn't find your user on graph.anime.plus. Add it there before running this.
https://graph.anime.plus/""")
    all_trs = graph_anime_page.find("table", {"class": "tablesorter"}).find("tbody").find_all("tr")
    # Remove non-scored entries; those which have `-`'s
    valid_trs = list(filter(lambda tr: tr.find_all("td")[-1].text != "-", all_trs))
    return valid_trs


def main(username, wait_time, cache_decay_time, display_name, status_list, output_settings):

    output_to_csv, output_graph = output_settings

    scraper = crawl(wait=wait_time, retry_max=3)
    jikan = jikanwrapper.Jikan()
    cache = Cache(cache_decay_time, jikan, scraper)

    # Remove non-scored entries
    valid_trs = get_graph_anime_trs(username, scraper)
    # Filter by status
    filtered_trs = list(filter(lambda tr: get_status(tr.find_all("td")[0]) is not None and get_status(tr.find_all("td")[0]) in status_list, valid_trs))
    # Create objects, pull score data from Jikan/MAL if necessary
    user_data = [list_item(tr, cache) for tr in filtered_trs]
    # remove items with no score, not useful to graph
    user_data = list(filter(lambda l_item: float(l_item.mal_average_rating) != float(0.0), user_data))

    if not user_data:
        print("User has no rating data.")
        sys.exit(1)

    update_json_file(cache.json_fullpath, cache.items)  # write all new items to cache

    output_name = f"{username}-{round(current_unix_time())}"

    if output_to_csv:
        with open(f"{output_name}.csv", 'w') as csv_w:
            csv_writer = writer(csv_w)
            for line in user_data:
                csv_writer.writerow([line.mal_id, line.status, line.user_rating, line.mal_average_rating])

    if output_graph:
        x_vals = []
        y_vals = []
        for l_item in user_data:
            x_vals.append(float(l_item.mal_average_rating))
            y_vals.append(float(l_item.user_rating))
        make_graph(x_vals, y_vals, output_name, username, display_name)

    return user_data


if __name__ == "__main__":
    username, wait_time, cache_decay_time, display_name, status_list, *output_settings = options()
    main(username, wait_time, cache_decay_time, display_name, status_list, output_settings)
    print("Done!")
