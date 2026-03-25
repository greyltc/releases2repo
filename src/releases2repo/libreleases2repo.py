import urllib.request
import urllib.error
import json


class Releases2Repo:
    hub = "github"
    owner = "greyltc"
    repo = "arch-packages"
    webserver_port = 59523
    webserver_host = "127.0.0.1"
    repo_name = f"{hub}_{owner}_{repo}"

    def __init__(
        self, hub=hub, owner=owner, repo=repo, port=webserver_port, host=webserver_host
    ):
        self.hub = hub
        self.owner = owner
        self.repo = repo
        self.webserver_port = port
        self.webserver_host = host
        self.repo_name = f"{hub}_{owner}_{repo}"

    def get_all_releases(self):
        all_releases = []

        if self.hub == "github":
            page = 1
            while True:
                url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases?per_page=100&page={page}"
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Python-urllib-Script"}
                )

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
