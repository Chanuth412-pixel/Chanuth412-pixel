
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
MAX_CONTRIBUTIONS = 8

START_MARKER = "<!-- OPEN_SOURCE_CONTRIBUTIONS:START -->"
END_MARKER = "<!-- OPEN_SOURCE_CONTRIBUTIONS:END -->"


def github_get(url):
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "open-source-profile",
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.load(response)


def format_count(number):
    if number >= 1000:
        return f"{number / 1000:.1f}k".replace(".0k", "k")
    return str(number)


def format_date(value):
    if not value:
        return "Date unavailable"

    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).strftime("%d %b %Y")


def clean_summary(body):
    if not body:
        return "Merged contribution to this project."

    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
    body = re.sub(r"`([^`]+)`", r"\1", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"(?m)^#+\s*", "", body)
    body = re.sub(r"\s+", " ", body).strip()

    if len(body) > 220:
        body = body[:217].rsplit(" ", 1)[0] + "..."

    return body or "Merged contribution to this project."


def get_category(item):
    labels = [
        label["name"].lower()
        for label in item.get("labels", [])
    ]

    text = (item.get("title", "") + " " + " ".join(labels)).lower()

    if any(x in text for x in ["documentation", "docs", "tutorial"]):
        return "Documentation"

    if any(x in text for x in ["bug", "fix"]):
        return "Bug Fix"

    if any(x in text for x in ["feature", "enhancement"]):
        return "Feature"

    return "Open Source"


def search_merged_prs():
    candidates = []

    # Search up to 1,000 matching PRs.
    for page in range(1, 11):
        query = f"is:pr is:merged author:{USERNAME}"

        params = urlencode({
            "q": query,
            "per_page": 100,
            "page": page,
            "sort": "updated",
            "order": "desc",
        })

        data = github_get(
            f"https://api.github.com/search/issues?{params}"
        )

        items = data.get("items", [])

        if not items:
            break

        for item in items:
            if "pull_request" not in item:
                continue

            repo_url = item.get("repository_url", "")
            parts = repo_url.rstrip("/").split("/")

            if len(parts) < 2:
                continue

            owner = parts[-2]
            repo = parts[-1]

            # Exclude repositories owned by the user.
            if owner.lower() == USERNAME.lower():
                continue

            candidates.append((item, owner, repo))

    # Sort by the actual PR closing/merge date.
    candidates.sort(
        key=lambda x: x[0].get("closed_at") or "",
        reverse=True,
    )

    return candidates


def get_repo_details(owner, repo, cache):
    full_name = f"{owner}/{repo}"

    if full_name not in cache:
        cache[full_name] = github_get(
            f"https://api.github.com/repos/{full_name}"
        )

    return cache[full_name]


def generate_contributions():
    candidates = search_merged_prs()

    repo_cache = {}
    contributions = []

    for item, owner, repo in candidates:
        if len(contributions) >= MAX_CONTRIBUTIONS:
            break

        details = get_repo_details(owner, repo, repo_cache)

        # Only public repositories owned by others.
        if details.get("private", True):
            continue

        full_name = details["full_name"]
        stars = details.get("stargazers_count", 0)
        forks = details.get("forks_count", 0)
        language = details.get("language") or "Not specified"

        merged_date = item.get("closed_at")

        contributions.append({
            "title": item["title"],
            "url": item["html_url"],
            "number": item["number"],
            "repo": full_name,
            "repo_url": details["html_url"],
            "summary": clean_summary(item.get("body")),
            "category": get_category(item),
            "stars": stars,
            "forks": forks,
            "language": language,
            "merged_date": merged_date,
        })

    return contributions


def generate_markdown(contributions):
    if not contributions:
        return "_No merged contributions to external public repositories found._"

    lines = []

    for item in contributions:
        lines.append(
            f'- **[{item["title"]}]({item["url"]})**'
            f' — {item["summary"]}'
        )

        metadata = [
            f'[{item["repo"]}]({item["repo_url"]})',
            f'⭐ {format_count(item["stars"])} stars',
            f'🍴 {format_count(item["forks"])} forks',
            item["language"],
            item["category"],
            f'PR #{item["number"]}',
            f'Merged {format_date(item["merged_date"])}',
        ]

        lines.append(
            "  <sub>" + " · ".join(metadata) + "</sub>"
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

    contributions = generate_contributions()

    generated = generate_markdown(contributions)

    updated = (
        content[:start]
        + "\n\n"
        + generated
        + "\n\n"
        + content[end:]
    )

    README.write_text(updated, encoding="utf-8")

    print(
        f"Updated README with {len(contributions)} "
        "external merged contributions."
    )


if __name__ == "__main__":
    update_readme()
