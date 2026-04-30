# releases2repo

[![PyPI - Version](https://img.shields.io/pypi/v/releases2repo.svg)](https://pypi.org/project/releases2repo)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/releases2repo.svg)](https://pypi.org/project/releases2repo)

-----

## Requirements
Arch Linux.

## Installation

```console
git clone https://aur.archlinux.org/python-releases2repo.git
cd python-releases2repo
makepkg -Cfis
```

## Usage

```console
$ systemctl start caddy-api
$ run0 r2repo --sync  # indexes the release artifacts and creates/updates a local cache
Total releases found: 28
Usable releases found: 2
$ r2repo --from-cache --caddy  # configures/starts/updates a caddy webserver for pacman from the local cache
Put the following three lines into your pacman.conf:
[github_greyltc_arch-packages]
SigLevel = Optional TrustAll
Server = http://127.0.0.1:59523/github_greyltc_arch-packages
# update your pacman.conf as above now
$ run0 pacman -Syu
:: Synchronizing package databases...
 github_greyltc_arch-packages   1241.0   B   404 KiB/s 00:00 [################################] 100%
 core is up to date
 extra is up to date
:: Starting full system upgrade...
 there is nothing to do
```

## Hacking

```console
python -m venv --without-pip --system-site-packages --clear venv
python -c 'import build; print(build.ProjectBuilder(".").build("editable", "venv"))'
source venv/bin/activate
python -m installer venv/*.whl
# hack here
deactivate
```

## License

`releases2repo` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
