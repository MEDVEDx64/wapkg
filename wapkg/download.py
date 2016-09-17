import hashlib

from sys import stdout
from urllib.request import urlopen


class Downloader(object):
    def __init__(self, quiet=False):
        self.quiet = quiet
        self._last_path = None

    # URLError is thrown in case of errors
    def go(self, link, path, action=None):
        with urlopen(link) as req:
            with open(path, 'wb') as f:
                if self.quiet:
                    f.write(req.read())
                else:
                    seg = 131072  # 128K
                    total = 0
                    dl_size = ''
                    dl_size_int = -1

                    if link.startswith('http'):
                        cl = req.info().get('Content-Length')
                        dl_size_int = int(int(cl) / 1024)
                        dl_size = '/' + str(dl_size_int)

                    while True:
                        chunk = req.read(seg)
                        total += int(len(chunk) / 1024)
                        msg = '- Downloading ' + link.split('/')[-1] + ', ' + str(total) + dl_size + ' KB'
                        if action:
                            action.update_progress(total, dl_size_int)

                        stdout.write('\r' + msg)
                        f.write(chunk)
                        if len(chunk) < seg:
                            break

                    print()  # newline
                    self._last_path = path

        return self

    # Raises RuntimeError when verifying fails
    def _verify(self, hexdigest, algo):
        if not hexdigest or not self._last_path:
            return

        hash = hashlib.new(algo)
        with open(self._last_path, 'rb') as f:
            hash.update(f.read())
        if not hash.hexdigest() == hexdigest:
            raise RuntimeError('Checksum does not match')

    def verify_sha1(self, hexdigest):
        self._verify(hexdigest, 'sha1')


class DownloadAction(object):
    def __init__(self, token):
        self.token = token

    def update_progress(self, current, total):
        pass
