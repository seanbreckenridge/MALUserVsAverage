import time
import requests

# Uses the wonderful https://jikan.moe/ to cache info about MAL Scores

class JikanException(Exception):
    """General exception for Jikan requests"""
    pass


class Jikan:

    ANIME = True
    MANGA = False

    def __init__(self):
        self.base_url = 'https://api.jikan.moe/v3'
        self.session = requests.Session()

    def get(self, id, option):
        url = "{}/{}/{}".format(self.base_url, 'anime' if option else 'manga', id)
        response = self.session.get(url)
        if response.status_code > 400:
            raise JikanException(f"id {id} failed with {response.status_code}")
        time.sleep(2.75) # comply with rate limit
        return response.json()

    # 0 is no score
    def get_score(self, id, option):
        return float(self.get(id, option)["score"])

if __name__ == "__main__":
    # Basic Tests
    j = Jikan()
    cowboy_bebop = j.get(1, Jikan.ANIME)
    print(cowboy_bebop["score"])
    print(cowboy_bebop["genre"])
    print(cowboy_bebop["opening_theme"])
