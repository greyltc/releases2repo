import sys

import tarfile
from os import listdir
import subprocess
from compression import zstd
from pathlib import Path
from urllib import request
from tempfile import TemporaryDirectory
from collections.abc import Sequence
import argparse
import io
import http.server
import socketserver

import releases2repo

from releases2repo import Releases2Repo

def run(user:str="greyltc", repo:str="arch-packages"):
    r = Releases2Repo()

    releases = r.get_all_releases(user, repo)
    print(f"Total releases found: {len(releases)}")
    package_urls = {}
    memfiles = {}
    pkgs = {}
    with TemporaryDirectory() as tdirt:
        tpatht = Path(tdirt)
        tfiles = tpatht / "files" / "repo"
        tdb = tpatht / "db" / "repo"
        tfiles.mkdir(parents=True, exist_ok=True)
        tdb.mkdir(parents=True, exist_ok=True)
        for release in reversed(releases):
            release_package_urls = {}
            with TemporaryDirectory() as tdirb:
                tpathb = Path(tdirb)
                has_repo = False
                got_files = False
                assets = release["assets"]
                for asset in assets:
                    if asset["name"].endswith(".pkg.tar.zst") and asset["content_type"] == "application/zstd":
                        release_package_urls[asset["name"]] = asset["browser_download_url"]
                    if asset["name"] == "repo.db" and asset["content_type"] == "application/zstd":
                        has_repo = True
                    if asset["name"] == "repo.files" and asset["content_type"] == "application/zstd":
                        fpath = tpathb / asset["name"]
                        dlrslt = request.urlretrieve(asset["browser_download_url"], fpath)
                        with tarfile.open(fpath, mode='r:zst') as tar_file:
                            tar_file.extractall(tpathb)
                            got_files = True
                        fpath.unlink()
                if has_repo and got_files:
                    for pname in tpathb.glob('*'):
                        descfile = pname / "desc"
                        with open(descfile, 'r') as file:
                            interesting_vars = ("%NAME%", "%VERSION%", "%FILENAME%")
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
                                        nextline = sline.strip('%')
                        if this["NAME"] in pkgs:
                            other_ver = pkgs[this["NAME"]]["VERSION"]
                            this_ver = this["VERSION"]
                            com_rslt = subprocess.run(['vercmp', other_ver, this_ver], text=True, capture_output=True)
                            code = int(com_rslt.stdout.strip())
                            if code < 0:
                                keep_it = True
                                # evict the out of date version
                                to_unlink = tdb / f'{this["NAME"]}-{pkgs[this["NAME"]]["VERSION"]}' / "desc"
                                to_unlink.unlink()
                                to_unlink = tfiles / f'{this["NAME"]}-{pkgs[this["NAME"]]["VERSION"]}' / "desc"
                                to_unlink.unlink()
                                to_unlink = tfiles / f'{this["NAME"]}-{pkgs[this["NAME"]]["VERSION"]}' / "files"
                                to_unlink.unlink()
                                to_rm = tfiles / f'{this["NAME"]}-{pkgs[this["NAME"]]["VERSION"]}'
                                to_rm.rmdir()
                                to_rm = tdb / f'{this["NAME"]}-{pkgs[this["NAME"]]["VERSION"]}'
                                to_rm.rmdir()
                            else:
                                keep_it = False
                        else:
                            keep_it = True
                        if keep_it:
                            pkgs[this["NAME"]] = {}
                            pkgs[this["NAME"]]["VERSION"] = this["VERSION"]
                            pkgs[this["NAME"]]["FILENAME"] = this["FILENAME"]
                            #versions[this["NAME"]] = this["VERSION"]
                            package_urls[this["FILENAME"]] = release_package_urls[this["FILENAME"]]
                            pnamedb = tdb / pname.name
                            pnamedb.mkdir(exist_ok=True)
                            descfile.copy_into(pnamedb)
                            pname.move_into(tfiles)
        if listdir(tdb):
            #repo_path = Path("repo.db.tar.zst")
            repo_path = tpatht / "repo.db.tar.zst"
            with tarfile.open(repo_path, mode='w:zst') as tf:
                for package in tdb.glob('*'):
                    tf.add(str(package), arcname=package.name)
            with open(repo_path, "rb") as fh:
                memfiles["repo.db"] = io.BytesIO(fh.read())
            #Path("repo.db").symlink_to(repo_path)

        if listdir(tfiles):
            #files_path = Path("repo.files.tar.zst")
            files_path = tpatht / "repo.files.tar.zst"
            with tarfile.open(files_path, mode='w:zst') as tf:
                for package in tfiles.glob('*'):
                    tf.add(str(package), arcname=package.name)
            with open(files_path, "rb") as fh:
                memfiles["repo.files"] = io.BytesIO(fh.read())
            #Path("repo.files").symlink_to(files_path)

    #if package_urls:
    #    print("Packages found:")
    #    print(str(dict(reversed(list(package_urls.items())))))

    class RedirectHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            # Example: Redirect a specific path
            rpath = self.path.lstrip("/")
            if rpath in package_urls:
                self.send_response(301)
                self.send_header('Location', package_urls[rpath])
                self.end_headers()
            elif rpath in memfiles:
                self.send_response(200)
                self.send_header("Content-type", "application/zstd")
                self.send_header("Content-length", memfiles[rpath].getbuffer().nbytes)
                self.end_headers()
                memfiles[rpath].seek(0)
                self.copyfile(memfiles[rpath], self.wfile)
            else:
                self.send_error(404, "nah")

    PORT = 8000
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), RedirectHandler) as httpd:
        print(f"Serving with redirects at http://localhost:{PORT}")
        httpd.serve_forever()

def main_parser() -> argparse.ArgumentParser:
    description = releases2repo.__doc__
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f'r3pcomms {releases2repo.__version__} ({",".join(releases2repo.__path__)})',
    )
    parser.add_argument(
        "--user",
        "-u",
        default="greyltc",
        help="owner of vcs repo"
    )
    parser.add_argument(
        "--repo",
        "-r",
        default="arch-packages",
        help="vcs repo name"
    )
    return parser

def main(cli_args: Sequence[str], prog: str | None = None) -> None:
    parser = main_parser()
    if prog:
        parser.prog = prog
    args = parser.parse_args(cli_args)


    run_args = {
        "user": args.user,
        "repo": args.repo,
    }
    run(**run_args)

def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:], "python -m r3pcomms")


__all__ = [
    "main",
    "main_parser",
]