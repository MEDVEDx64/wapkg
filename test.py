from wapkg.repo import Repository


def main():
    repo = Repository()
    if '3.7.2.1' not in repo.list_distributions():
        print('Installing Battle Pack...')
        ok, msg = repo.install_dist_from_file('../WALauncher/server/distributions/3.7.2.1-battle-pack-minimal.wadist')
        print(msg)
        if not ok:
            return

    dist = repo.get_distribution('3.7.2.1 Battle Pack Minimal')
    if 'schemekit' in dist.list_packages():
        print('Detected previous installation of schemekit. Removing...')
        ok, msg = dist.remove_package('schemekit')
        print(msg)
        if not ok:
            return

    print('Download & install...')
    ok, msg = dist.install_package_by_name('schemekit', repo.get_sources())
    print(msg)

if __name__ == '__main__':
    main()
