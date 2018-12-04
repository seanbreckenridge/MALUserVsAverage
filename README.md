# MALUserVsAverage
Uses graph.anime.plus to generate a graph that shows correlation between the user and average score on MyAnimeList. Each blip on the graph x-coordinate is your score, and y-coordinate is the weighted MAL score. There is no grand takeaway from this, its just fun to look at.

<img src="https://raw.githubusercontent.com/purplepinapples/MALUserVsAverage/master/images/1.png" width=400> <img src="https://raw.githubusercontent.com/purplepinapples/MALUserVsAverage/master/images/2.png" width=400>

Since the MAL API has been down for a while, this uses [graph.anime.plus](https://graph.anime.plus/) to get data from users [MyAnimeList](https://myanimelist.net/) account.

graph.anime.plus does not list scores for MAL entries under 50 members; [Jikan](https://jikan.moe/) is used to get MAL scores for those.

### Installation

1) Submit a MAL Username to graph.anime.plus, and wait for them to finish processing it.
2) `git clone https://github.com/purplepinapples/MALUserVsAverage`
3) `pip3 install --user numpy matplotlib scipy`
4) Run! A basic execution would be `python3 run.py --username <your_username> --anime --graph`, or any of the following for different results:

Create a graph; only plot anime the user has completed:

`python3 run.py -u USERNAME --anime --graph --filter C`

Create a graph; only take into account MAL scores cached locally in the last day:

`python3 run.py -u USERNAME --anime --graph --cache-decay-time 1`

Create a graph; plot the users *manga* and include their username in the Graph's title.

`python3 run.py -u USERNAME --manga --graph --display-name`

Generate a CSV file of all anime the user has scored, ordered `MAL ID, Status, User Rating, Mal Rating`:

`python3 run.py -u USERNAME --anime --csv`


Tested in python versions `3.6.5` and `3.7.1`.

```
usage: python3 driver.py [-h] -u USERNAME (-a | -m)
                       [--cache-decay-time CACHE_DECAY_TIME] [-w WAIT_TIME]
                       [-f FILTER] [-c] [-g] [-d]

Create user vs average MAL Score correlation graphs.

required arguemnts::
  -u USERNAME, --username USERNAME     The MAL User for who the list/graph
                                       should be generated.
  -a, --anime                          Create a graph/csv file for this users
                                       anime.
  -m, --manga                          Create a graph/csv file for this users
                                       manga.

optional arguments:
  -h, --help                           show this help message and exit
  --cache-decay-time CACHE_DECAY_TIME  Number of days scores should stay in
                                       cache before they are refresed. If not
                                       provided, uses 2 weeks.
  -w WAIT_TIME, --wait-time WAIT_TIME  Wait time between (manual; non-API)
                                       scrape requests. Default and
                                       recomended is 5 (seconds).
  -f FILTER, --filter FILTER           Filter by Status,
                                       e.g. '-f WC' would filter so output
                                       contained only Watching and Completed.
                                       W: Currently Watching
                                       C: Completed
                                       O: On-Hold
                                       D: Dropped
                                       P: Plan to Watch

(optional) output options (Generates both if nothing specified): :
  -c, --csv                            Output a CSV File.
  -g, --graph                          Output a graph.
  -d, --display-name                   Display the username on the graph.
```
