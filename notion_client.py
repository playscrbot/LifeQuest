import json
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"

class NotionAPIError(Exception):
    pass

class NotionClient:
    def __init__(self, token, timeout=25):
        self.token = (token or "").strip()
        self.timeout = timeout
        if not self.token:
            raise ValueError("A Notion integration token is required.")

    def _request(self, method, path, payload=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            API_ROOT + path, data=body, method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                data = json.loads(exc.read().decode("utf-8", errors="replace"))
                message = data.get("message") or data.get("code") or str(data)
            except Exception:
                message = "No error details returned."
            if exc.code in (401, 403):
                raise NotionAPIError(
                    "Notion rejected this token or the integration lacks access. "
                    "Check the token and share the database with your integration."
                ) from exc
            if exc.code == 404:
                raise NotionAPIError(
                    "Notion could not find this database/page, or it is not shared with your integration."
                ) from exc
            if exc.code == 429:
                raise NotionAPIError("Notion rate limit reached. Wait a moment and try again.") from exc
            raise NotionAPIError(f"Notion API error {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise NotionAPIError(f"Could not reach Notion: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise NotionAPIError("Notion returned an unexpected response.") from exc

    def get_user(self):
        return self._request("GET", "/users/me")

    def get_database(self, database_id):
        return self._request("GET", f"/databases/{urllib.parse.quote(database_id, safe='')}")

    def get_page(self, page_id):
        return self._request("GET", f"/pages/{urllib.parse.quote(page_id, safe='')}")

    def query_data_source(self, data_source_id):
        results, cursor = [], None
        while True:
            payload = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            response = self._request(
                "POST",
                f"/data_sources/{urllib.parse.quote(data_source_id, safe='')}/query",
                payload,
            )
            batch = response.get("results", [])
            if not isinstance(batch, list):
                raise NotionAPIError("Notion returned an invalid database query response.")
            results.extend(batch)
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
            if not cursor:
                break
        return results

    def get_block_children(self, block_id):
        results, cursor = [], None
        while True:
            query = "?page_size=100"
            if cursor:
                query += "&start_cursor=" + urllib.parse.quote(cursor, safe="")
            response = self._request(
                "GET",
                f"/blocks/{urllib.parse.quote(block_id, safe='')}/children{query}",
            )
            batch = response.get("results", [])
            if not isinstance(batch, list):
                raise NotionAPIError("Notion returned an invalid page-content response.")
            results.extend(batch)
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
            if not cursor:
                break
        return results


def _plain(items):
    if not isinstance(items, list):
        return ""
    parts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("plain_text", "")
        href = item.get("href")
        if not href:
            text_data = item.get("text") or {}
            link_data = text_data.get("link") or {}
            href = link_data.get("url")
        parts.append(f"{value} ({href})" if href else value)
    return "".join(parts)


def _property_value(prop):
    """Turn common Notion property types into readable note metadata."""
    if not isinstance(prop, dict):
        return ""
    kind = prop.get("type", "")
    value = prop.get(kind)
    if kind in ("title", "rich_text"):
        return _plain(value)
    if kind in ("select", "status"):
        return value.get("name", "") if isinstance(value, dict) else ""
    if kind == "multi_select":
        return ", ".join(x.get("name", "") for x in (value or []) if isinstance(x, dict))
    if kind == "date":
        if isinstance(value, dict):
            start = value.get("start", "")
            end = value.get("end", "")
            return f"{start} – {end}" if end else start
        return ""
    if kind == "url":
        return value or ""
    if kind == "email":
        return value or ""
    if kind == "phone_number":
        return value or ""
    if kind == "number":
        return "" if value is None else str(value)
    if kind == "checkbox":
        return "Yes" if value else "No"
    if kind == "people":
        return ", ".join(
            (person.get("name") or person.get("id", "")) for person in (value or [])
            if isinstance(person, dict)
        )
    if kind == "formula" and isinstance(value, dict):
        formula_type = value.get("type")
        formula_value = value.get(formula_type)
        return str(formula_value) if formula_value is not None else ""
    return ""


def _page_title(page):
    props = page.get("properties") or {}

    if isinstance(props, dict):
        for prop in props.values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                title = _property_value(prop).strip()
                if title:
                    return title

    # Fallback to top-level title
    top_title = page.get("title")
    if isinstance(top_title, list):
        top_title = _plain(top_title)
    elif isinstance(top_title, dict):
        top_title = _property_value(top_title)

    if isinstance(top_title, str) and top_title.strip():
        return top_title.strip()

    return ""


def _property_content(page):
    """Include useful database properties such as Description/Content in the note body."""
    props = page.get("properties") or {}
    if not isinstance(props, dict):
        return []
    lines = []
    for name, prop in props.items():
        if not isinstance(prop, dict) or prop.get("type") == "title":
            continue
        value = _property_value(prop).strip()
        if not value:
            continue
        # Include all readable properties; users often store the note itself in a
        # Description, Content, Notes, or Summary rich-text database column.
        lines.append(f"{name}: {value}")
    return lines


def _block_text(block):
    kind = block.get("type", "")
    data = block.get(kind) or {}
    if kind in (
        "paragraph", "heading_1", "heading_2", "heading_3",
        "bulleted_list_item", "numbered_list_item", "to_do",
        "quote", "callout", "toggle",
    ):
        value = _plain(data.get("rich_text", []))
        if kind == "heading_1":
            return "# " + value
        if kind == "heading_2":
            return "## " + value
        if kind == "heading_3":
            return "### " + value
        if kind == "bulleted_list_item":
            return "• " + value
        if kind == "numbered_list_item":
            return "1. " + value
        if kind == "to_do":
            return ("[x] " if data.get("checked") else "[ ] ") + value
        if kind == "quote":
            return "> " + value
        return value
    if kind == "code":
        return _plain(data.get("rich_text", []))
    if kind == "divider":
        return "────────"
    if kind in ("bookmark", "embed"):
        return data.get("url", "")
    if kind == "image":
        source = data.get("external") or data.get("file") or {}
        return "[Image: " + (source.get("url") or "embedded image") + "]"
    if kind == "child_page":
        return data.get("title", "Untitled child page")
    if kind == "child_database":
        return data.get("title", "Child database")
    if kind == "file":
        source = data.get("external") or data.get("file") or {}
        return "[File: " + (source.get("url") or "attached file") + "]"
    if kind == "pdf":
        source = data.get("external") or data.get("file") or {}
        return "[PDF: " + (source.get("url") or "attached PDF") + "]"
    return ""

def _collect_blocks(client, parent_id, depth=0, max_depth=4):
    if depth > max_depth:
        return []

    lines = []

    for block in client.get_block_children(parent_id):
        value = _block_text(block)

        if value:
            lines.append(("  " * depth) + value)

        if block.get("has_children") and depth < max_depth:
            lines.extend(
                _collect_blocks(
                    client,
                    block["id"],
                    depth + 1,
                    max_depth
                )
            )

    return lines

def page_to_note(page, client):
    title = _page_title(page)

    if not title and page.get("id"):
        detailed_page = client.get_page(page["id"])
        page = {**page, **detailed_page}
        title = _page_title(page)

    property_lines = _property_content(page)
    block_lines = _collect_blocks(client, page["id"])

    body_parts = []

    if property_lines:
        body_parts.append("\n".join(property_lines))

    if block_lines:
        body_parts.append("\n".join(block_lines))

    body = "\n\n".join(body_parts).strip()

    return {
        "external_id": page["id"],
        "title": title or "Untitled Notion note",
        "body": body,
        "source_url": page.get("url", ""),
        "source_updated_at": page.get("last_edited_time", ""),
    }