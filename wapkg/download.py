from sys import stdout
from urllib.request import urlopen


class Downloader(object):
    def __init__(self, quiet=False):
        self.quiet = quiet

    # URLError is thrown in case of errors
    def go(self, link, path):
        with urlopen(link) as req:
            with open(path, 'wb') as f:
                if self.quiet:
                    f.write(req.read())
                else:
                    seg = 131072  # 128K
                    total = 0
                    dl_size = ''
                    if link.startswith('http'):
                        cl = req.info().get('Content-Length')
                        dl_size = '/' + str(int(int(cl) / 1024))

                    while True:
                        chunk = req.read(seg)
                        total += int(len(chunk) / 1024)
                        msg = '- Downloading ' + link.split('/')[-1] + ', ' + str(total) + dl_size + ' KB'
                        stdout.write('\r' + msg)
                        f.write(chunk)
                        if len(chunk) < seg:
                            break

                    print()  # newline
