import os


def clean_cache(repo):
    path = os.path.join(repo, 'cache')
    for x in os.listdir(path):
        os.unlink(os.path.join(path, x))
