import urllib.request
import urllib.error
import json

class Releases2Repo:

    def get_all_releases(self, owner, repo):
        all_releases = []
        page = 1
        
        while True:
            url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=100&page={page}"
            req = urllib.request.Request(url, headers={"User-Agent": "Python-urllib-Script"})
            
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
                
        return all_releases
