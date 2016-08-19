import os
import sys
import json
import sqlite3

from zipfile import ZipFile

from .distro import Distribution

DEFAULT_SETTINGS = {
    'sources': [
        'https://themassacre.org/ftp/public/Worms/proto/'
    ]
}


class Repository(object):
    def __init__(self):
        self.wd = '.'
        if not os.path.exists('portable'):
            if sys.platform == 'win32':
                self.wd = os.path.join(os.getenv('APPDATA'), 'wapkg')
            else:
                self.wd = os.path.join(os.getcwd(), '.wapkg')

            if not os.path.exists(self.wd):
                os.mkdir(self.wd)
            sf = os.path.join(self.wd, 'settings.json')
            if not os.path.exists(sf):
                with open(sf, 'w') as f:
                    f.write(json.dumps(DEFAULT_SETTINGS))

        self.settings = {}
        with open(os.path.join(self.wd, 'settings.json'), 'r') as f:
            self.settings = json.loads(f.read())
        if 'path' in self.settings:
            self.wd = self.settings['path']

    def list_distributions(self):
        distro = []
        for d in os.listdir(self.wd):
            if os.path.exists(os.path.join(self.wd, d, '.wadist')):
                distro.append(d)

        return distro

    def get_distribution(self, name):
        return Distribution(os.path.join(self.wd, name))

    def get_sources(self):
        return self.settings['sources']

    def install_dist_from_file(self, path, name=None):
        with ZipFile(path) as zf:
            wadist = json.loads(zf.read('wadist.json').decode('utf-8'))
            if not wadist['version'] == 1:
                return False, 'Unsupported distribution format'

            target = wadist['suggestedName']
            if name:
                target = name
            target = os.path.join(self.wd, target)
            if os.path.exists(target):
                return False, 'A distribution with such name is already exists'

            repo = os.path.join(target, '.wadist')
            os.makedirs(os.path.join(repo, 'cache'))
            with open(os.path.join(repo, 'version'), 'w') as vf:
                vf.write('1')
            with sqlite3.connect(os.path.join(repo, 'packages.db')) as conn:
                c = conn.cursor()
                c.execute('CREATE TABLE packages(name char(64) primary key not null,revision uint not null)')
                c.execute('CREATE TABLE paths('
                          'path char(512) not null primary key,'
                          'dir int(1) not null default 0,'
                          'package char(64) not null,'
                          'foreign key (package) references packages(name) on delete cascade'
                          ');')
                conn.commit()

            for n in zf.namelist():
                if n.startswith('wadist'):
                    continue
                zf.extract(n, target)

        return True, 'Success'
