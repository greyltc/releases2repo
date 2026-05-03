import sys


from pathlib import Path

from collections.abc import Sequence
import argparse

import releases2repo

from releases2repo import Releases2Repo


def run(
    hub: str = Releases2Repo.hub,
    owner: str = Releases2Repo.owner,
    repo: str = Releases2Repo.repo,
    port: int = Releases2Repo.webserver_port,
    host: str = Releases2Repo.webserver_host,
    from_cache: bool = False,
    caddy_api_port: int = Releases2Repo.caddy_api_port,
    caddy_api_host: str = Releases2Repo.caddy_api_host,
    storage: Path = Releases2Repo.local_storage_path,
    sync: bool = False,
    serve: bool = False,
    caddy: bool = False,
    gen_pacman_config: bool = False,
) -> None:
    r = Releases2Repo(
        hub=hub,
        owner=owner,
        repo=repo,
        port=port,
        host=host,
        storage=storage,
    )
    if gen_pacman_config:
        r.print_pacman_config()
        sys.exit(0)

    if sync or serve or from_cache:
        col = r.collect_repos(to_local=sync, to_memory=serve, from_cache=from_cache)

        if caddy:
            r.configure_caddy(col["package_urls"], caddy_api_host, caddy_api_port)
        elif serve:
            r.run_webserver(col["package_urls"], col["memfiles"])


def main_parser() -> argparse.ArgumentParser:
    description = releases2repo.__doc__
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f'releases2repo {releases2repo.__version__} ({",".join(releases2repo.__path__)})',
    )
    parser.add_argument(
        "--type",
        "-t",
        default=Releases2Repo.hub,
        choices=["github", "gitlab"],
        help="type of hub to fetch from",
    )
    parser.add_argument(
        "--owner",
        "-o",
        default=Releases2Repo.owner,
        help="owner of vcs repo",
    )
    parser.add_argument(
        "--repo",
        "-r",
        default=Releases2Repo.repo,
        help="vcs repo name",
    )
    parser.add_argument(
        "--port",
        "-p",
        default=Releases2Repo.webserver_port,
        help="Local webserver port to listen on",
    )
    parser.add_argument(
        "--bind",
        "-b",
        default=Releases2Repo.webserver_host,
        help="Local webserver hostname/ip to listen on",
    )
    parser.add_argument(
        "--gen-pacman-config",
        "-g",
        action="store_true",
        help="Generate a pacman configuration stub",
    )
    parser.add_argument(
        "--from-cache",
        action="store_true",
        help="Use cached data instead of fetching from the hub, requires --sync to have been run at least once before to populate the cache",
    )
    parser.add_argument(
        "--caddy-api-port",
        "-c",
        default=Releases2Repo.caddy_api_port,
        help="Access caddy's api via this port",
    )
    parser.add_argument(
        "--caddy-api-host",
        "-H",
        default=Releases2Repo.caddy_api_host,
        help="Access caddy's api via this hostname/ip",
    )
    parser.add_argument(
        "--local",
        "-l",
        default=Releases2Repo.local_storage_path,
        help="Local place to store pacman database files",
    )
    parser.add_argument(
        "--sync",
        "-s",
        action="store_true",
        help="Update the local storage cache with the latest release data from the hub",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run a webserver to serve the repo",
    )
    parser.add_argument(
        "--caddy",
        action="store_true",
        help="Configure a caddy webserver (via its API) to serve the repo, requires --sync previously",
    )
    return parser


def main(cli_args: Sequence[str], prog: str | None = None) -> None:
    parser = main_parser()
    if prog:
        parser.prog = prog
    args = parser.parse_args(cli_args)

    if args.caddy:
        args.from_cache = True

    run_args = {
        "hub": args.type,
        "owner": args.owner,
        "repo": args.repo,
        "port": args.port,
        "host": args.bind,
        "gen_pacman_config": args.gen_pacman_config,
        "from_cache": args.from_cache,
        "caddy_api_port": args.caddy_api_port,
        "caddy_api_host": args.caddy_api_host,
        "storage": Path(args.local),
        "sync": args.sync,
        "serve": args.serve,
        "caddy": args.caddy,
    }
    run(**run_args)


def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:] + ["--serve"], "python -m releases2repo")


__all__ = [
    "main",
    "main_parser",
]
