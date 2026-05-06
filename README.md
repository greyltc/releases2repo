# releases2repo

[![PyPI - Version](https://img.shields.io/pypi/v/releases2repo.svg)](https://pypi.org/project/releases2repo)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/releases2repo.svg)](https://pypi.org/project/releases2repo)

-----
## AI
I dictated to Microsoft's Copilot thing to generate a lot of the code in the `configure_caddy` function in `src/releases2repo/libreleases2repo.py` because I didn't feel like reading Caddy's api and configuration documentation. Looks like it did a pretty crap job, but it has fooled me into thinking it's working as I intend.

## Requirements
Arch Linux.

## Installation

```console
$ git clone https://aur.archlinux.org/python-releases2repo.git
$ cd python-releases2repo
$ makepkg -Cfis
```

## Usage
```console
$ r2repo --help
usage: r2repo [-h] [--version] [--type {github,gitlab}] [--owner OWNER]
              [--repo REPO] [--port PORT] [--bind BIND] [--gen-pacman-config]
              [--from-cache] [--caddy-api-port CADDY_API_PORT]
              [--caddy-api-host CADDY_API_HOST] [--local LOCAL] [--sync]
              [--serve] [--caddy]

take package files from vcs releases and turn them into a repo that pacman can
use

options:
  -h, --help            show this help message and exit
  --version, -V         show program's version number and exit
  --type, -t {github,gitlab}
                        type of hub to fetch from (default: github)
  --owner, -o OWNER     owner of vcs repo (default: greyltc)
  --repo, -r REPO       vcs repo name (default: arch-packages)
  --port, -p PORT       Local webserver port to listen on (default: 59523)
  --bind, -b BIND       Local webserver hostname/ip to listen on (default:
                        127.0.0.1)
  --gen-pacman-config, -g
                        Generate a pacman configuration stub (default: False)
  --from-cache          Use cached data instead of fetching from the hub,
                        requires --sync to have been run at least once before
                        to populate the cache (default: False)
  --caddy-api-port, -c CADDY_API_PORT
                        Access caddy's api via this port (default: 2019)
  --caddy-api-host, -H CADDY_API_HOST
                        Access caddy's api via this hostname/ip (default:
                        127.0.0.1)
  --local, -l LOCAL     Local place to store pacman database files (default:
                        /var/lib/r2repo)
  --sync, -s            Update the local storage cache with the latest release
                        data from the hub (default: False)
  --serve               Run a webserver to serve the repo (default: False)
  --caddy               Configure a caddy webserver (via its API) to serve the
                        repo, requires --sync previously (default: False)
```

## Example

```console
$ systemctl start caddy-api
$ run0 r2repo --sync  # indexes the release artifacts and creates/updates a local cache
Using: github/greyltc/arch-packages
Total releases found: 28
Usable releases found: 2
$ r2repo --caddy  # configures/starts/updates a caddy webserver for pacman from the local cache
Using: github/greyltc/arch-packages
$ r2repo --gen-pacman-config | run0 tee -a /etc/pacman.conf
[github_greyltc_arch-packages]
SigLevel = Optional TrustAll
Server = http://127.0.0.1:59523/github_greyltc_arch-packages
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
$ python -m venv --without-pip --system-site-packages --clear venv
$ python -c 'import build; print(build.ProjectBuilder(".").build("editable", "venv"))'
$ source venv/bin/activate
$ python -m installer venv/*.whl
$ # hack here
$ deactivate
```

## License

`releases2repo` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
