#!/usr/bin/env python3

import os
import subprocess

from sys import argv, platform
from wapkg.repo import Repository

usage = 'Usage: ' + argv[0] + ' <distro> [args ...]'

if __name__ == '__main__':
    if len(argv) < 2:
        print(usage)
        exit()

    if argv[1] == '-h' or argv[1] == '--help':
        print(usage)
        exit()

    repo = Repository()
    if argv[1] not in repo.list_distributions():
        print('No such distro: ' + argv[1])
        exit(1)

    dist = repo.get_distribution(argv[1])
    null = open(os.devnull, 'w')
    args = [os.path.join(dist.wd, 'WA.exe')] + argv[2:]
    if platform == 'win32':
        subprocess.call(args, stdout=null, stderr=null)
    else:
        subprocess.call(['wine'] + args, stdout=null, stderr=null)
