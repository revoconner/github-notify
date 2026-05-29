import httpx
from typing import Optional

API_BASE = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str):
        self._client = httpx.Client(
            base_url=API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "github-tray",
            },
            timeout=30.0,
        )

    def close(self):
        self._client.close()

    def get_me(self):
        r = self._client.get("/user")
        r.raise_for_status()
        return r.json()

    def list_owned_repos(self):
        all_repos = []
        page = 1
        while True:
            r = self._client.get(
                "/user/repos",
                params={"affiliation": "owner", "per_page": 100, "page": page},
            )
            r.raise_for_status()
            batch = r.json()
            all_repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return all_repos

    def search(self, query: str, max_pages: int = 2):
        items = []
        page = 1
        while page <= max_pages:
            r = self._client.get(
                "/search/issues",
                params={"q": query, "per_page": 100, "page": page},
            )
            r.raise_for_status()
            data = r.json()
            batch = data.get("items", [])
            items.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return items

    def list_notifications(self, since_iso: Optional[str] = None):
        params = {"per_page": 50, "all": "false"}
        if since_iso:
            params["since"] = since_iso
        r = self._client.get("/notifications", params=params)
        r.raise_for_status()
        try:
            poll_interval = int(r.headers.get("X-Poll-Interval", "60"))
        except ValueError:
            poll_interval = 60
        return r.json(), poll_interval

    def get_url(self, url: str):
        r = self._client.get(url)
        r.raise_for_status()
        return r.json()
