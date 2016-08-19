import json

from urllib.request import urlopen
from urllib.error import URLError
from urllib.parse import urljoin


# Returns repo index dictionary object, or None in case of failure
def fetch_index(repo_url):
    index = {}
    try:
        with urlopen(urljoin(repo_url, 'index.json')) as index_req:
            index = json.loads(index_req.read().decode('utf-8'))
    except URLError:
        return None

    if 'repo' not in index or not index['repo'] == 'wapkg' or not index['version'] == 1:
        return None

    return index
