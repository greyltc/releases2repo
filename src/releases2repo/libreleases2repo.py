from pathlib import Path
import sys
import os
import urllib.request
import urllib.error
import urllib.parse
import json
import subprocess
from tempfile import TemporaryDirectory
import tarfile
from os import listdir
import io
import http.server
import socketserver

from pyparsing import col


class Releases2Repo:
    hub = "github"
    owner = "greyltc"
    repo = "arch-packages"
    webserver_port = 59523
    webserver_host = "127.0.0.1"
    caddy_api_port = 2019
    caddy_api_host = "127.0.0.1"
    repo_name = f"{hub}_{owner}_{repo}"
    local_storage_path = Path("/var/lib/r2repo/")
    reverse_proxy = True  # if True, package files will be proxied through the webserver. if False, package urls will be redirected to the hub.
    extra_headers = {}  # extra headers to add to requests

    def __init__(
        self,
        hub=hub,
        owner=owner,
        repo=repo,
        port=webserver_port,
        host=webserver_host,
        storage=local_storage_path,
    ):
        self.hub = hub
        self.owner = owner
        self.repo = repo
        self.webserver_port = port
        self.webserver_host = host
        self.repo_name = f"{hub}_{owner}_{repo}"
        self.local_storage_path = storage
        github_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        if github_token:
            self.extra_headers["Authorization"] = f"Bearer {github_token}"
        # self.extra_headers["Authorization"] = "Bearer github_pat_abcde"  # hardcoded for testing

    def collect_repos(self, to_local=False, to_memory=False, from_cache=False) -> dict:
        results = {}
        package_urls = {}
        if from_cache:
            try:
                with open(
                    self.local_storage_path / f"{self.repo_name}_urls.json", "r"
                ) as fh:
                    package_urls = json.load(fh)
            except FileNotFoundError:
                if not to_local:
                    print(
                        "Error: Cache file not found. Run with --sync to populate the cache.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
        if to_local or to_memory:
            memfiles = {}
            pkgs = {}
            releases = self.get_all_releases()
            print(f"Total releases found: {len(releases)}")
            usable_releases = 0

            with TemporaryDirectory() as tdirt:
                tpatht = Path(tdirt)
                tfiles = tpatht / "files" / "repo"
                tdb = tpatht / "db" / "repo"
                tfiles.mkdir(parents=True, exist_ok=True)
                tdb.mkdir(parents=True, exist_ok=True)
                for release in reversed(releases):
                    asset_info = {}
                    with TemporaryDirectory() as tdirb:
                        tpathb = Path(tdirb)
                        has_repo = False
                        got_files = False
                        assets = release["assets"]
                        for asset in assets:
                            if (
                                asset["name"].endswith(".pkg.tar.zst")
                                and asset["content_type"] == "application/zstd"
                            ):
                                asset_info[asset["name"]] = {}
                                asset_info[asset["name"]]["burl"] = asset[
                                    "browser_download_url"
                                ]
                                asset_info[asset["name"]]["url"] = asset["url"]
                            if (
                                asset["name"] == "repo.db"
                                and asset["content_type"] == "application/zstd"
                            ):
                                has_repo = True
                            if (
                                asset["name"] == "repo.files"
                                and asset["content_type"] == "application/zstd"
                            ):
                                req = urllib.request.Request(asset["url"])
                                req.headers.update(
                                    {"Accept": "application/octet-stream"}
                                )
                                for header, value in self.extra_headers.items():
                                    req.headers.update({header: value})
                                try:
                                    with urllib.request.urlopen(req) as response:
                                        with tarfile.open(
                                            fileobj=io.BytesIO(response.read()),
                                            mode="r:zst",
                                        ) as tar_file:
                                            tar_file.extractall(tpathb)
                                            got_files = True
                                except urllib.error.HTTPError as e:
                                    pass  # raise RuntimeError(f"Failed to fetch {asset['browser_download_url']}: {e}")
                        if has_repo and got_files:
                            usable_releases += 1
                            for pname in tpathb.glob("*"):
                                descfile = pname / "desc"
                                with open(descfile, "r") as file:
                                    interesting_vars = (
                                        "%NAME%",
                                        "%VERSION%",
                                        "%FILENAME%",
                                    )
                                    nextline = ""
                                    this = {}
                                    for line in file:
                                        sline = line.strip()
                                        if nextline:
                                            this[nextline] = sline
                                            if nextline == "VERSION":
                                                # we don't need to read past "%VERSION%" for now
                                                this[nextline] = sline
                                                break
                                            nextline = ""
                                        else:
                                            if sline in interesting_vars:
                                                nextline = sline.strip("%")
                                if this["NAME"] in pkgs:
                                    other_ver = pkgs[this["NAME"]]["VERSION"]
                                    this_ver = this["VERSION"]
                                    com_rslt = subprocess.run(
                                        ["vercmp", other_ver, this_ver],
                                        text=True,
                                        capture_output=True,
                                    )
                                    version_compare_code = int(com_rslt.stdout.strip())
                                    if version_compare_code <= 0:
                                        keep_it = True
                                        # evict the out of date version
                                        del package_urls[pkgs[this["NAME"]]["FILENAME"]]
                                        to_unlink = (
                                            tdb
                                            / f'{this["NAME"]}-{pkgs[this["NAME"]]["VERSION"]}'
                                            / "desc"
                                        )
                                        to_unlink.unlink()
                                        to_unlink = (
                                            tfiles
                                            / f'{this["NAME"]}-{pkgs[this["NAME"]]["VERSION"]}'
                                            / "desc"
                                        )
                                        to_unlink.unlink()
                                        to_unlink = (
                                            tfiles
                                            / f'{this["NAME"]}-{pkgs[this["NAME"]]["VERSION"]}'
                                            / "files"
                                        )
                                        to_unlink.unlink()
                                        to_rm = (
                                            tfiles
                                            / f'{this["NAME"]}-{pkgs[this["NAME"]]["VERSION"]}'
                                        )
                                        to_rm.rmdir()
                                        to_rm = (
                                            tdb
                                            / f'{this["NAME"]}-{pkgs[this["NAME"]]["VERSION"]}'
                                        )
                                        to_rm.rmdir()
                                    else:
                                        keep_it = False
                                else:
                                    keep_it = True
                                if keep_it:
                                    pkgs[this["NAME"]] = {}
                                    pkgs[this["NAME"]]["VERSION"] = this["VERSION"]
                                    pkgs[this["NAME"]]["FILENAME"] = this["FILENAME"]
                                    package_urls[this["FILENAME"]] = asset_info[
                                        this["FILENAME"]
                                    ]
                                    pnamedb = tdb / pname.name
                                    pnamedb.mkdir(exist_ok=True)
                                    descfile.copy_into(pnamedb)
                                    pname.move_into(tfiles)

                # if package_urls:
                #    print("Packages found:")
                #    print(str(dict(reversed(list(asset_info.items())))))
                print(f"Usable releases found: {usable_releases}")

                if to_local:
                    self.local_storage_path.mkdir(parents=True, exist_ok=True)
                    with open(
                        self.local_storage_path / f"{self.repo_name}_urls.json", "w"
                    ) as fh:
                        json.dump(package_urls, fh, indent=4)

                dbs = []
                files = []
                if listdir(tdb):
                    repo_path = tpatht / f"{self.repo_name}.db"
                    with tarfile.open(repo_path, mode="w:zst") as tf:
                        for package in tdb.glob("*"):
                            tf.add(str(package), arcname=package.name)
                    if to_memory:
                        with open(repo_path, "rb") as fh:
                            memfiles[f"{self.repo_name}.db"] = io.BytesIO(fh.read())
                        memfiles[f"{self.repo_name}.db"].seek(0)
                    if to_local:
                        repo_path.copy(
                            self.local_storage_path
                            / repo_path.with_suffix(".db.tar.zst").name
                        )
                        try:
                            dbs.append(
                                (self.local_storage_path / repo_path.name).symlink_to(
                                    repo_path.with_suffix(".db.tar.zst").name
                                )
                            )
                        except FileExistsError as e:
                            pass

                if listdir(tfiles):
                    files_path = tpatht / f"{self.repo_name}.files"
                    with tarfile.open(files_path, mode="w:zst") as tf:
                        for package in tfiles.glob("*"):
                            tf.add(str(package), arcname=package.name)
                    if to_memory:
                        with open(files_path, "rb") as fh:
                            memfiles[f"{self.repo_name}.files"] = io.BytesIO(fh.read())
                        memfiles[f"{self.repo_name}.files"].seek(0)
                    if to_local:
                        files_path.copy(
                            self.local_storage_path
                            / files_path.with_suffix(".files.tar.zst").name
                        )
                        try:
                            files.append(
                                (self.local_storage_path / files_path.name).symlink_to(
                                    files_path.with_suffix(".files.tar.zst").name
                                )
                            )
                        except FileExistsError as e:
                            pass
            if memfiles:
                results["memfiles"] = memfiles
            if dbs:
                results["dbs"] = dbs
            if files:
                results["files"] = files
        if package_urls:
            results["package_urls"] = package_urls

        return results

    def print_pacman_config(self):
        print(f"[{self.repo_name}]")
        print("SigLevel = Optional TrustAll")
        print(
            f"Server = http://{self.webserver_host}:{self.webserver_port}/{self.repo_name}"
        )

    def configure_caddy(self, package_urls, caddy_api_host, caddy_api_port):
        # almost all of this function was written by some stupid AI because I didn't feel like learning CADDY's config stuff
        # and so I have no idea what's going on in here, so if it breaks, good luck figuring out why
        package_routes = []
        for package_name, package_info in package_urls.items():
            upstream_url = package_info["url"]
            parsed = urllib.parse.urlparse(upstream_url)
            upstream_host = parsed.hostname or ""
            upstream_port = parsed.port or (443 if parsed.scheme == "https" else 80)
            upstream_dial = f"{upstream_host}:{upstream_port}"
            upstream_uri = parsed.path
            if parsed.query:
                upstream_uri = f"{upstream_uri}?{parsed.query}"

            proxy_handler = {
                "handler": "reverse_proxy",
                "upstreams": [{"dial": upstream_dial}],
                "headers": {
                    "request": {
                        "set": {
                            "Host": [parsed.netloc],
                            "Accept": ["application/octet-stream"],
                        }
                    }
                },
            }
            if parsed.scheme == "https":
                proxy_handler["transport"] = {"protocol": "http", "tls": {}}
            if self.extra_headers.get("Authorization"):
                proxy_handler["headers"]["request"]["set"]["Authorization"] = [
                    self.extra_headers["Authorization"]
                ]

            package_routes.append(
                {
                    "handle": [
                        {"handler": "rewrite", "uri": upstream_uri},
                        proxy_handler,
                    ],
                    "match": [{"path": [f"/{self.repo_name}/{package_name}"]}],
                }
            )

        caddy_config = {
            "apps": {
                "http": {
                    "servers": {
                        f"{self.repo_name}": {
                            "listen": [f"{self.webserver_host}:{self.webserver_port}"],
                            "routes": package_routes
                            + [
                                {
                                    "match": [{"path": [f"/{self.repo_name}/*"]}],
                                    "handle": [
                                        {
                                            "handler": "rewrite",
                                            "strip_path_prefix": f"/{self.repo_name}",
                                        },
                                        {
                                            "handler": "file_server",
                                            "root": str(self.local_storage_path),
                                            "browse": {},
                                        },
                                    ],
                                }
                            ],
                        }
                    }
                }
            }
        }

        base = f"http://{caddy_api_host}:{caddy_api_port}/config"

        def ensure_root_config():
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(f"{base}/", method="GET")
                ) as response:
                    raw = response.read().decode("utf-8").strip()
                    if raw and json.loads(raw) is not None:
                        return True
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                print(
                    f"Failed to query Caddy root config: {e.code} {e.reason}: {err_body}"
                )
                return False
            except urllib.error.URLError as e:
                eargs = e.args[0]
                if eargs.errno == 111:
                    print(f"ERROR: {eargs.strerror}", sys.stderr)
                    print(
                        f"Is caddy's api server running on {base.rstrip('/config')}? Hint:"
                    )
                    print("systemctl start caddy-api")
                    sys.exit(1)
            except json.JSONDecodeError:
                pass

            # If root config is null/empty, initialize it so path traversal works.
            try:
                req = urllib.request.Request(
                    f"{base}/",
                    data=json.dumps({}).encode("utf-8"),
                    method="PATCH",
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req):
                    return True
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                # Some Caddy states cannot traverse /config yet; bootstrap via /load.
                if e.code in (400, 404):
                    try:
                        bootstrap = {"apps": {"http": {"servers": {}}}}
                        req = urllib.request.Request(
                            f"http://{caddy_api_host}:{caddy_api_port}/load",
                            data=json.dumps(bootstrap).encode("utf-8"),
                            method="POST",
                            headers={"Content-Type": "application/json"},
                        )
                        with urllib.request.urlopen(req):
                            return True
                    except urllib.error.HTTPError as e2:
                        err_body2 = e2.read().decode("utf-8", errors="replace")
                        print(
                            f"Failed to initialize Caddy root config: {e2.code} {e2.reason}: {err_body2}"
                        )
                        return False
                    except urllib.error.URLError as e2:
                        print(f"Failed to initialize Caddy root config: {e2.reason}")
                        return False

                print(
                    f"Failed to initialize Caddy root config: {e.code} {e.reason}: {err_body}"
                )
                return False
            except urllib.error.URLError as e:
                print(f"Failed to initialize Caddy root config: {e.reason}")
                return False

        def ensure_object(path):
            try:
                with urllib.request.urlopen(urllib.request.Request(path, method="GET")):
                    return True
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    err_body = e.read().decode("utf-8", errors="replace")
                    print(
                        f"Failed to query Caddy config path {path}: {e.code} {e.reason}: {err_body}"
                    )
                    return False

            try:
                req = urllib.request.Request(
                    path,
                    data=json.dumps({}).encode("utf-8"),
                    method="PUT",
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req):
                    return True
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                print(
                    f"Failed to create Caddy config path {path}: {e.code} {e.reason}: {err_body}"
                )
                return False

        # clear out the old config
        # req = urllib.request.Request(f"http://{caddy_api_host}:{caddy_api_port}/config/apps/http/servers/releases2repo", method="DELETE")

        if not ensure_root_config():
            return

        if not ensure_object(f"{base}/apps"):
            return
        if not ensure_object(f"{base}/apps/http"):
            return
        if not ensure_object(f"{base}/apps/http/servers"):
            return

        repo_server_config = caddy_config["apps"]["http"]["servers"][self.repo_name]
        shared_server_name = "releases2repo"
        servers_path = (
            f"http://{caddy_api_host}:{caddy_api_port}/config/apps/http/servers"
        )

        current_servers = {}
        try:
            with urllib.request.urlopen(
                urllib.request.Request(servers_path, method="GET")
            ) as response:
                raw = response.read().decode("utf-8")
                current_servers = json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(
                f"Failed to query Caddy servers config: {e.code} {e.reason}: {err_body}"
            )
            return
        except urllib.error.URLError as e:
            print(f"Failed to query Caddy servers config: {e.reason}")
            return

        if not isinstance(current_servers, dict):
            print(
                "Failed to configure Caddy: /config/apps/http/servers is not an object"
            )
            return

        shared_server = current_servers.get(shared_server_name, {})
        if not isinstance(shared_server, dict):
            print(
                f"Failed to configure Caddy: /config/apps/http/servers/{shared_server_name} is not an object"
            )
            return

        def route_belongs_to_repo(route):
            if not isinstance(route, dict):
                return False
            for match_obj in route.get("match", []):
                if not isinstance(match_obj, dict):
                    continue
                for path in match_obj.get("path", []):
                    if isinstance(path, str) and path.startswith(f"/{self.repo_name}/"):
                        return True
            return False

        existing_routes = shared_server.get("routes", [])
        if not isinstance(existing_routes, list):
            existing_routes = []
        new_repo_routes = repo_server_config.get("routes", [])
        if not isinstance(new_repo_routes, list):
            new_repo_routes = []

        # Replace only this repo's route namespace and preserve all other routes.
        preserved_routes = [r for r in existing_routes if not route_belongs_to_repo(r)]
        shared_server["routes"] = preserved_routes + new_repo_routes

        listen_addr = f"{self.webserver_host}:{self.webserver_port}"
        listen_addrs = shared_server.get("listen", [])
        if not isinstance(listen_addrs, list):
            listen_addrs = []
        if listen_addr not in listen_addrs:
            listen_addrs.append(listen_addr)
        shared_server["listen"] = listen_addrs

        current_servers[shared_server_name] = shared_server

        req = urllib.request.Request(
            servers_path,
            data=json.dumps(current_servers).encode("utf-8"),
            method="PATCH",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as response:
                if 200 <= response.status < 300:
                    pass
                else:
                    print(
                        f"Failed to configure Caddy: {response.status} {response.reason}"
                    )
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"Failed to configure Caddy: {e.code} {e.reason}: {err_body}")
        except urllib.error.URLError as e:
            print(f"Failed to configure Caddy: {e.reason}")

    def run_webserver(self, package_urls, memfiles):
        do_reverse_proxy = self.reverse_proxy
        extra_headers = self.extra_headers
        repo_name = self.repo_name

        class RedirectHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                request_path = urllib.parse.urlparse(self.path).path
                prefix = f"/{repo_name}/"
                if not request_path.startswith(prefix):
                    self.send_error(404, "nah")
                    return
                rpath = request_path[len(prefix) :]
                if rpath in package_urls:
                    if do_reverse_proxy:
                        # reverse proxy for package files served by hub
                        url = package_urls[rpath]["url"]
                        req = urllib.request.Request(url)
                        req.headers.update({"Accept": "application/octet-stream"})
                        if "User-Agent" in self.headers:
                            req.headers.update(
                                {"User-Agent": self.headers["User-Agent"]}
                            )
                        if "Authorization" in self.headers:
                            req.headers.update(
                                {"Authorization": self.headers["Authorization"]}
                            )
                        for header, value in extra_headers.items():
                            req.headers.update({header: value})
                        try:
                            with urllib.request.urlopen(req) as response:
                                # Forward the response status and headers
                                self.send_response(response.status)
                                for header, value in response.getheaders():
                                    if header.lower() not in (
                                        "transfer-encoding",
                                        "connection",
                                    ):
                                        self.send_header(header, value)
                                self.end_headers()

                                self.copyfile(response, self.wfile)

                        except urllib.error.HTTPError as e:
                            self.send_error(e.code, e.reason)
                        except urllib.error.URLError as e:
                            self.send_error(502, f"Bad Gateway: {e.reason}")
                    else:
                        # redirect for package files served by hub
                        url = package_urls[rpath]["burl"]
                        self.send_response(302)
                        self.send_header("Location", url)
                        self.end_headers()
                # serve pacman metadata files from memory
                elif rpath in memfiles:
                    self.send_response(200)
                    self.send_header("Content-type", "application/zstd")
                    self.send_header(
                        "Content-length", memfiles[rpath].getbuffer().nbytes
                    )
                    self.end_headers()
                    memfiles[rpath].seek(0)
                    self.copyfile(memfiles[rpath], self.wfile)
                else:
                    self.send_error(404, "nah")

        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(
            (self.webserver_host, self.webserver_port), RedirectHandler
        ) as httpd:
            print(
                f"Repo server running at http://{self.webserver_host}:{self.webserver_port}"
            )
            print("")
            print("Add the following three lines to your pacman.conf:")
            print(f"[{self.repo_name}]")
            print("SigLevel = Optional TrustAll")
            print(
                f"Server = http://{self.webserver_host}:{self.webserver_port}/{self.repo_name}"
            )
            print("")
            print("Serving...(press Ctrl+c to stop)...")

            httpd.serve_forever()

    def fetch(self, url: str, output: str) -> None:

        try:
            with urllib.request.urlopen(url) as response:
                data = response.read()
                with open(output, "wb") as fh:
                    fh.write(data)
        except urllib.error.HTTPError as e:
            print(f"Failed to fetch {url}: {e}")

    def get_all_releases(self):
        all_releases = []

        if self.hub == "github":
            page = 1
            while True:
                url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases?per_page=100&page={page}"
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "getthereleases/0.95",
                        "Accept": "application/vnd.github.v3+json",
                    },
                )
                for header, value in self.extra_headers.items():
                    req.headers.update({header: value})

                try:
                    with urllib.request.urlopen(req) as response:
                        data = json.loads(response.read().decode("utf-8"))

                        # If the list is empty, we've hit the end of the history
                        if not data:
                            break

                        all_releases.extend(data)
                        page += 1
                except urllib.error.HTTPError as e:
                    print(f"Stopped at page {page}: {e}")
                    break
        elif self.hub == "gitlab":
            raise ValueError(f"{self.hub} is not supported yet.")
        else:
            raise ValueError(f"{self.hub}: unknown hub type.")

        return all_releases
