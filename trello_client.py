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
        boards = self._get("/members/me/boards", {
            "filter": "open",
            "fields": "id,name,url,closed",
            "lists": "none"
        })

        if not isinstance(boards, list):
            raise TrelloAPIError(f"Unexpected boards response. Expected a list, got {type(boards).__name__}: {boards}")

        for index, board in enumerate(boards):
            if not isinstance(board, dict):
                raise TrelloAPIError(f"Invalid board at index {index}: expected a dictionary, got {type(board).__name__}")

            if "id" not in board or "name" not in board:
                raise TrelloAPIError(f"Board at index {index} is missing required fields. Received: {board}")

        return boards

    def get_lists(self, board_id):
        """Return all lists on a board, including archived lists."""
        if not isinstance(board_id, str) or not board_id.strip():
            raise ValueError("A valid Trello board ID is required.")

        encoded_board_id = urllib.parse.quote(board_id.strip(), safe="")

        lists = self._get(
            f"/boards/{encoded_board_id}/lists",
            {
                "filter": "all",
                "fields": "id,name,closed"
            }
        )
        
        if not isinstance(lists, list):
            raise TrelloAPIError(
                "Trello returned an unexpected response while loading board lists. "
                f"Expected a list, received {type(lists).__name__}."
            )

        validated_lists = []
        
        for index, item in enumerate(lists):
            if not isinstance(item, dict):
                raise TrelloAPIError(
                    f"Invalid list at index {index}: expected a dictionary, "
                    f"received {type(item).__name__}."
                )
                
            missing = [
                field for field in ("id", "name")
                if field not in item
            ]
            
            if missing:
                raise TrelloAPIError(
                    f"Trello list at index {index} is missing fields: "
                    f"{', '.join(missing)}. Received: {item}"
                )

            if not isinstance(item["id"], str) or not item["id"].strip():
                raise TrelloAPIError(f"Trello list at index {index} has an invalid ID.")

            if not isinstance(item["name"], str):
                raise TrelloAPIError(f"Trello list at index {index} has an invalid name.")

            validated_lists.append({
                "id": item["id"],
                "name": item["name"],
                "closed": bool(item.get("closed", False))
            })

        return validated_lists

    def get_cards(self, board_id):
        cards = self._get(f"/boards/{urllib.parse.quote(board_id, safe='')}/cards", {
            "filter": "all",
            "fields": "id,name,desc,due,dueComplete,closed,idList,url,shortUrl,dateLastActivity,labels",
            "limit": 1000
        })
        
        print("TRELLO RAW RESPONSE:")
        print(json.dumps(cards[:3] if isinstance(cards, list) else cards, indent=4))

        if not isinstance(cards, list):
            raise TrelloAPIError("Trello returned an unexpected response while loading cards.")
            
        for index, card in enumerate(cards):
            if not isinstance(card, dict):
                raise TrelloAPIError(f"Invalid card at index {index}: expected a dictionary.")
                
            if "id" not in card or "name" not in card or "idList" not in card:
                raise TrelloAPIError(f"Card at index {index} is missing required fields: {card}")
            
        return cards