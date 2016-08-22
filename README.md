# wapkg
A package manager for Worms: Armageddon.

Manage multiple W:A versions (a.k.a. distributions), download and install
packages (like RubberWorm, etc).

How does it works?
------------------

*Distributions* is downloaded and placed into *repository* (`%appdata%\wapkg` on Windows, or `~/.wapkg`
on *nix systems). This behavior can be overridden by placing an empty `portable` file
in the working directory, nor by adding `path` value to repo's `settings.json` file.

The packages is installed separately for each distro.

Usage
-----

*wapkg* comes with *Worms Armageddon Packaging Tool (wapt)*. Refer to
`python wapt.py --help` for usage details.

Requirements
------------

Python 3.

Moar
----

`warun.py` - instantly run an installed distro.
