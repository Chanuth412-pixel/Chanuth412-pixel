
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USERNAME = os.getenv("GITHUB_USERNAME", "Chanuth412-pixel")
TOKEN = os.environ["GITHUB_TOKEN"]

README = Path("README.md")

START_MARKER = "<!-- OPEN_SOURCE_CONTRIBUTIONS:START -->"
END_MARKER = "<!-- OPEN_SOURCE_CONTRIBUTIONS:END -->"

# Curated descriptions for contributions where the PR body
# does not contain a suitable summary.
MANUAL_OVERRIDES = {
    "https://github.com/pypa/build/pull/1281": {
        "repo": "pypa/build",
        "number": 1281,
        "title": "Fixed the missing src directory in tutorial",
        "summary": (
            "Fixed the Getting Started tutorial by replacing "
            "`mkdir src/mypackage` with `mkdir -p src/mypackage`, "
            "ensuring the missing parent directory is created automatically."
        ),
        "category": "Documentation",
        "merged_date": "13 Nov 2026",
        "sort_date": "2026-11-13T00:00:00Z",
    }
}


def github_get(url):
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "open-source-contributions-readme",
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.load(response)


def clean_summary(body):
    if not body:
        return ""

    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    body = re.sub(r"(?m)^#{1,6}\s*", "", body)
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
    body = re.sub(r"`([^`]+)`", r"\1", body)
    body = re.sub(r"(?m)^\s*[-*]\s+", "", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"[*_~]", "", body)
    body = re.sub(r"\s+", " ", body).strip()

    if len(body) > 240:
        body = body[:237].rsplit(" ", 1)[0] + "..."

    return body


def format_date(value):
    if not value:
        return "Date unavailable"

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).strftime("%d %b %Y")
    except ValueError:
        return "Date unavailable"


def get_merged_prs():
    query = f"is:pr is:merged author:{USERNAME}"

    url = (
        "https://api.github.com/search/issues?"
        + urlencode({
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": 100,
        })
    )

    results = github_get(url)

    entries = {}

    for item in results.get("items", []):
        if "pull_request" not in item:
            continue

        pr_url = item["html_url"]
        repo = item["repository_url"].split("/repos/")[-1]

        override = MANUAL_OVERRIDES.get(pr_url, {})

        labels = [
            label["name"]
            for label in item.get("labels", [])
        ]

        merged_at = item.get("closed_at") or ""

        entries[pr_url] = {
            "url": pr_url,
            "repo": override.get("repo", repo),
            "number": item["number"],
            "title": override.get("title", item["title"]),
            "summary": (
                override.get("summary")
                or clean_summary(item.get("body", ""))
                or "Merged contribution to this project."
            ),
            "category": (
                override.get("category")
                or (", ".join(labels[:2]) if labels else "Open source")
            ),
            "date": (
                override.get("merged_date")
                or format_date(merged_at)
            ),
            "sort_date": merged_at,
        }

    # Include the first contribution even if GitHub search
    # has not indexed the newly merged PR yet.
    for pr_url, override in MANUAL_OVERRIDES.items():
        if pr_url not in entries:
            entries[pr_url] = {
                "url": pr_url,
                **override,
                "date": override["merged_date"],
            }

    return sorted(
        entries.values(),
        key=lambda item: item["sort_date"],
        reverse=True,
    )


def generate_markdown(entries):
    if not entries:
        return "_No merged pull requests found yet._"

    lines = []

    for entry in entries[:8]:
        lines.append(
            f'- **[{entry["title"]}]({entry["url"]})**'
            f' — {entry["summary"]}'
        )

        lines.append(
            f'  <sub>'
            f'[{entry["repo"]}](https://github.com/{entry["repo"]})'
            f' · {entry["category"]}'
            f' · PR #{entry["number"]}'
            f' · Merged {entry["date"]}'
            f'</sub>'
        )

        lines.append("")

    return "\n".join(lines).strip()


def update_readme():
    content = README.read_text(encoding="utf-8")

    if content.count(START_MARKER) != 1:
        raise ValueError("Missing or duplicate START marker.")

    if content.count(END_MARKER) != 1:
        raise ValueError("Missing or duplicate END marker.")

    start = content.index(START_MARKER) + len(START_MARKER)
    end = content.index(END_MARKER)

    if start >= end:
        raise ValueError("Contribution markers are incorrectly positioned.")

    entries = get_merged_prs()
    generated = generate_markdown(entries)

    updated = (
        content[:start]
        + "\n\n"
        + generated
        + "\n\n"
        + content[end:]
    )

    README.write_text(updated, encoding="utf-8")

    print(f"Updated README with {len(entries)} merged contributions.")


if __name__ == "__main__":
    update_readme()
