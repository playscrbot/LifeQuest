import json
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://api.trello.com/1"

class TrelloAPIError(Exception):
    pass

class TrelloClient:
    def __init__(self, api_key, token, timeout=25):
        self.api_key = api_key.strip()
        self.token = token.strip()
        self.timeout = timeout
        if not self.api_key or not self.token:
            raise ValueError("Both Trello API key and token are required.")

    def _get(self, path, params=None):
        query = dict(params or {})
        query.update({"key": self.api_key, "token": self.token})
        url = f"{API_ROOT}{path}?{urllib.parse.urlencode(query)}"
        request = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "LifeQuest/0.2"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code in (401, 403):
                raise TrelloAPIError("Trello rejected the credentials or read permissions. Check the API key and read-only token.") from exc
            if exc.code == 429:
                raise TrelloAPIError("Trello rate limit reached. Wait a moment and try again.") from exc
            raise TrelloAPIError(f"Trello API error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise TrelloAPIError(f"Could not reach Trello: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise TrelloAPIError("Trello returned an unexpected response.") from exc

    def get_member(self):
        return self._get("/members/me", {"fields": "fullName,username"})

    def get_boards(self):
        return self._get("/members/me/boards", {
            "filter": "open", "fields": "id,name,url,closed", "lists": "false"
        })

    def get_lists(self, board_id):
        return self._get(
            f"/boards/{urllib.parse.quote(board_id, safe='')}/lists", 
            {
                "filter": "open", 
                "fields": "id, name, closed"
            }
        )

    def get_cards(self, board_id):
        return self._get(f"/boards/{urllib.parse.quote(board_id, safe='')}/cards", {
            "filter": "all",
            "fields": "id,name,desc,due,dueComplete,closed,idList,url,shortUrl,dateLastActivity,labels",
            "limit": 1000
        })