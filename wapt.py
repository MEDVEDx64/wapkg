#!/usr/bin/env python3

# Worms Armageddon Packaging Tool (wapt)

import os

from sys import argv
from wapkg import remote
from wapkg.repo import Repository
from wapkg.version import get_version

help_msg = """
Worms Armageddon Packaging Tool (wapt)
Manage multiple W:A versions (a.k.a. distributions) and easily add packages to them.

- usage:

""" + argv[0] + """ install <distro> [packages|files ...] - add package(s) to distro
""" + argv[0] + """ remove <distro> [packages ...] - remove package(s) from distro
""" + argv[0] + """ dist-install <distro|file> [suggested_name] - install new distro
""" + argv[0] + """ dist-exterminate <distro> - uninstall distribution

""" + argv[0] + """ packages <distro> - list installed packages
""" + argv[0] + """ packages-available <distro> - list packages available for download
""" + argv[0] + """ dists - list installed distributions
""" + argv[0] + """ dists-available - list distribution available for download

""" + argv[0] + """ init - create distro repository, if it isn't done yet (optional, only required in case \
if you need to do some pre-configuration)

""" + argv[0] + """ help - show this message and exit
""" + argv[0] + """ version - show toolkit version and exit
"""


def print_help():
    print(help_msg)


def main():
    try:
        cmd = argv[1]
        if cmd == '-h' or cmd == '--help' or cmd == 'help':
            print_help()
            return

        elif cmd == 'init':
            Repository()

        elif cmd == 'install':
            repo = Repository()
            if argv[2] not in repo.list_distributions():
                print("Distribution '" + argv[2] + "' is not installed.")
                return

            dist = repo.get_distribution(argv[2])
            for pkg in argv[3:]:
                ok, msg = False, ''
                if os.path.exists(pkg) and os.path.isfile(pkg):
                    print("Installing '" + pkg + "'...")
                    ok, msg = dist.install_package_from_file(pkg)
                else:
                    print("Downloading & installing '" + pkg + "'...")
                    ok, msg = dist.install_package_by_name(pkg, repo.get_sources())
                if not ok:
                    print('FAILED: ' + msg)

        elif cmd == 'dist-install':
            ok, msg = False, ''
            suggested_name = None
            if len(argv) > 3:
                suggested_name = argv[3]
            pr = "'..."
            if suggested_name:
                pr = "' as '" + suggested_name + "'..."

            repo = Repository()
            if os.path.exists(argv[2]) and os.path.isfile(argv[2]):
                print("Installing distibution '" + argv[2] + pr)
                ok, msg, dn = repo.install_dist_from_file(argv[2], suggested_name)
            else:
                print("Downloading & installing '" + argv[2] + pr)
                ok, msg, dn = repo.install_dist_by_name(argv[2], repo.get_sources(), suggested_name)
            if not ok:
                print('FAILED: ' + msg)

        elif cmd == 'remove':
            repo = Repository()
            if argv[2] not in repo.list_distributions():
                print("Distribution '" + argv[2] + "' is not installed.")
                return

            for pkg in argv[3:]:
                print("Removing '" + pkg + "'...")
                ok, msg = repo.get_distribution(argv[2]).remove_package(pkg)
                if not ok:
                    print('FAILED: ' + msg)

        elif cmd == 'dist-exterminate':
            repo = Repository()
            if argv[2] not in repo.list_distributions():
                print("Distribution '" + argv[2] + "' is not installed.")
                return

            print("Warning! Distribution '" + argv[2] + "' is about to be completely erased, " +
                  'including all unmanaged user data. Are you sure want to continue? [y/N]')
            if not input().lower() == 'y':
                print('Aborted.')
                return
            repo.get_distribution(argv[2]).exterminate()
            print('Okay.')

        elif cmd == 'dists':
            dists = []
            for d in Repository().list_distributions():
                dists.append(d)
            dists.sort()
            for d in dists:
                print(d)

        elif cmd == 'packages':
            repo = Repository()
            if argv[2] not in repo.list_distributions():
                print("Distribution '" + argv[2] + "' is not installed.")
                return

            packages = []
            dist = repo.get_distribution(argv[2])
            for pkg in dist.list_packages():
                packages.append(pkg + ', revision ' + str(dist.get_package_revision(pkg)))

            packages.sort()
            for pkg in packages:
                print(pkg)

        elif cmd == 'dists-available':
            sources = Repository().get_sources()
            dists = []
            for src in sources:
                index = remote.fetch_index(src)
                if not index:
                    continue
                for d in index['distributions']:
                    if d not in dists:
                        dists.append(d)

            dists.sort()
            for x in dists:
                print(x)

        elif cmd == 'packages-available':
            repo = Repository()
            if argv[2] not in repo.list_distributions():
                print("Distribution '" + argv[2] + "' is not installed.")
                return

            dist = repo.get_distribution(argv[2])
            sources = repo.get_sources()
            packages = {}
            pkgs_bundle = []

            for src in sources:
                index = remote.fetch_index(src)
                if not index:
                    continue
                pkgs = index['packages']
                pkgs_bundle.append(pkgs)
                for pkg in pkgs:
                    rev = -1
                    pkg_ = remote.select_pkg(index['packages'][pkg], dist.get_version_string())
                    if not pkg_:
                        continue
                    if 'revision' in pkg_:
                        rev = pkg_['revision']
                    if pkg in packages:
                        if rev > packages[pkg]:
                            packages[pkg] = rev
                    else:
                        packages[pkg] = rev

            out = []
            for x in packages:
                if not remote.trace_pkg_deps(pkgs_bundle, dist.get_version_string(), x):
                    continue
                rev_str = ', revision ' + str(packages[x])
                if packages[x] < 0:
                    rev_str = ' (virtual package)'
                out.append(x + rev_str)

            out.sort()
            for x in out:
                print(x)

        elif cmd == 'version':
            print(get_version())

        else:
            print_help()

    except IndexError:
        print_help()

if __name__ == '__main__':
    main()
