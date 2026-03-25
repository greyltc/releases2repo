# releases2repo

[![PyPI - Version](https://img.shields.io/pypi/v/releases2repo.svg)](https://pypi.org/project/releases2repo)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/releases2repo.svg)](https://pypi.org/project/releases2repo)

-----

## Table of Contents

- [Installation](#installation)
- [License](#license)

## Installation

```console
git clone https://aur.archlinux.org/python-releases2repo.git
cd python-releases2repo
makepkg -Cfi
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
