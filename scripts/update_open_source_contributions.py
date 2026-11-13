
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

# --------------------------------------------------
# Configuration
# --------------------------------------------------

USERNAME = os.getenv("GITHUB_USERNAME", "Chanuth412-pixel")
TOKEN = os.environ["GITHUB_TOKEN"]

README = Path("README.md")

MIN_STARS = 500
MAX_CONTRIBUTIONS = 8
MAX_SEARCH_PAGES = 10

START_MARKER = "<!-- OPEN_SOURCE_CONTRIBUTIONS:START -->"
END_MARKER = "<!-- OPEN_SOURCE_CONTRIBUTIONS:END -->"


# --------------------------------------------------
# GitHub API
# --------------------------------------------------

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


# --------------------------------------------------
# Formatting helpers
# --------------------------------------------------

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


def clean_summary(body, title):
    """
    Extract only a short summary from the PR description.
    Never display the complete PR body.
    """

    if not body:
        return title

    body = html.unescape(body)

    # Remove comments, code blocks and images.
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    body = re.sub(r"```.*?```", " ", body, flags=re.S)
    body = re.sub(r"!\[.*?\]\(.*?\)", " ", body)

    # Keep link text, remove Markdown formatting.
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
    body = re.sub(r"`([^`]+)`", r"\1", body)
    body = re.sub(r"<[^>]+>", " ", body)

    lines = body.splitlines()
    meaningful_lines = []

    ignored_headings = {
        "description",
        "summary",
        "overview",
        "test plan",
        "testing",
        "checklist",
        "changes",
        "what does this pr do?",
        "why is this change needed?",
    }

    for line in lines:
        line = line.strip()

        if not line:
            if meaningful_lines:
                break
            continue

        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s*", "", line)
        line = re.sub(r"^>\s*", "", line)
        line = re.sub(r"^\[[ xX]\]\s*", "", line)

        if line.lower().rstrip(":") in ignored_headings:
            continue

        if re.match(
            r"^(closes|fixes|resolves)\s+#\d+",
            line,
            re.IGNORECASE,
        ):
            continue

        meaningful_lines.append(line)

    if not meaningful_lines:
        return title

    # Use the first meaningful paragraph only.
    paragraph = " ".join(meaningful_lines)
    paragraph = re.sub(r"\s+", " ", paragraph).strip()

    # Extract the first sentence.
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)

    summary = sentences[0]

    # Include a second sentence only when the first is too short.
    if len(summary) < 55 and len(sentences) > 1:
        candidate = summary + " " + sentences[1]

        if len(candidate) <= 180:
            summary = candidate

    # Hard limit on displayed summary length.
    if len(summary) > 180:
        summary = summary[:177].rsplit(" ", 1)[0] + "..."

    return summary or title


def get_category(title, labels):
    text = (
        title + " " +
        " ".join(label["name"] for label in labels)
    ).lower()

    if any(word in text for word in [
        "documentation", "docs", "tutorial"
    ]):
        return "Documentation"

    if any(word in text for word in [
        "bug", "fix", "broken", "error"
    ]):
        return "Bug Fix"

    if any(word in text for word in [
        "feature", "enhancement", "add support"
    ]):
        return "Feature"

    if any(word in text for word in [
        "test", "testing"
    ]):
        return "Testing"

    return "Code Contribution"


# --------------------------------------------------
# Search merged pull requests
# --------------------------------------------------

def search_merged_prs():

    candidates = []

    query = f"is:pr is:merged author:{USERNAME}"

    for page in range(1, MAX_SEARCH_PAGES + 1):

        params = urlencode({
            "q": query,
            "per_page": 100,
            "page": page,
            "sort": "updated",
            "order": "desc",
        })

        url = (
            "https://api.github.com/search/issues?"
            + params
        )

        data = github_get(url)

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

            # Exclude repositories owned by you.
            if owner.lower() == USERNAME.lower():
                continue

            candidates.append((item, owner, repo))

        if len(items) < 100:
            break

    return candidates


# --------------------------------------------------
# Repository information
# --------------------------------------------------

def get_repo_details(owner, repo, cache):

    full_name = f"{owner}/{repo}"

    if full_name not in cache:

        url = (
            f"https://api.github.com/repos/"
            f"{full_name}"
        )

        cache[full_name] = github_get(url)

    return cache[full_name]


# --------------------------------------------------
# Collect qualifying contributions
# --------------------------------------------------

def generate_contributions():

    candidates = search_merged_prs()

    repo_cache = {}
    contributions = []

    print(f"Found {len(candidates)} merged PR candidates.")

    for item, owner, repo in candidates:

        details = get_repo_details(
            owner,
            repo,
            repo_cache
        )

        # Public repositories only.
        if details.get("private", True):
            continue

        # Exclude repositories owned by the user.
        if owner.lower() == USERNAME.lower():
            continue

        stars = details.get("stargazers_count", 0)

        # Strictly more than 500 stars.
        if stars <= MIN_STARS:
            continue

        # Fetch actual PR details and merge timestamp.
        pr_url = item.get("pull_request", {}).get("url")

        if not pr_url:
            continue

        pr = github_get(pr_url)

        merged_at = pr.get("merged_at")

        # Confirm that the PR was actually merged.
        if not merged_at:
            continue

        title = pr.get("title") or item.get("title", "")

        body = pr.get("body") or ""

        summary = clean_summary(body, title)

        language = (
            details.get("language") or "Not specified"
        )

        forks = details.get("forks_count", 0)

        category = get_category(
            title,
            pr.get("labels", [])
        )

        contributions.append({
            "title": title,
            "url": pr.get("html_url", item["html_url"]),
            "number": pr.get("number", item["number"]),
            "repo": details["full_name"],
            "repo_url": details["html_url"],
            "summary": summary,
            "category": category,
            "stars": stars,
            "forks": forks,
            "language": language,
            "merged_at": merged_at,
        })

    # Newest merged contributions first.
    contributions.sort(
        key=lambda x: x["merged_at"],
        reverse=True
    )

    return contributions[:MAX_CONTRIBUTIONS]


# --------------------------------------------------
# Generate visually improved README section
# --------------------------------------------------

def generate_markdown(contributions):

    if not contributions:
        return (
            "<p align='center'>"
            "<i>No qualifying merged contributions found yet.</i>"
            "</p>"
        )

    rows = []

    for item in contributions:

        title = html.escape(item["title"])
        summary = html.escape(item["summary"])
        repo = html.escape(item["repo"])
        repo_url = html.escape(item["repo_url"], quote=True)
        pr_url = html.escape(item["url"], quote=True)
        language = html.escape(item["language"])
        category = html.escape(item["category"])

        stars = format_count(item["stars"])
        forks = format_count(item["forks"])

        date = format_date(item["merged_at"])

        rows.append(f"""
<tr>
<td>

<strong>
<a href="{pr_url}">{title}</a>
</strong>

<br/>

<a href="{repo_url}"><strong>{repo}</strong></a>

&nbsp; ⭐ {stars} stars
&nbsp; · &nbsp; 🍴 {forks} forks
&nbsp; · &nbsp; <code>{language}</code>

<br/><br/>

{summary}

<br/><br/>

<sub>
{category}
&nbsp; · &nbsp; PR #{item["number"]}
&nbsp; · &nbsp; Merged {date}
</sub>

</td>
</tr>
""")

    return (
        '<table align="center" width="100%">\n'
        + "\n".join(rows)
        + "\n</table>"
    )


# --------------------------------------------------
# Update README
# --------------------------------------------------

def update_readme():

    if not README.exists():
        raise FileNotFoundError("README.md not found.")

    content = README.read_text(encoding="utf-8")

    if content.count(START_MARKER) != 1:
        raise ValueError(
            "Missing or duplicate START marker."
        )

    if content.count(END_MARKER) != 1:
        raise ValueError(
            "Missing or duplicate END marker."
        )

    start = (
        content.index(START_MARKER)
        + len(START_MARKER)
    )

    end = content.index(END_MARKER)

    if start >= end:
        raise ValueError(
            "Contribution markers are incorrectly positioned."
        )

    contributions = generate_contributions()

    generated = generate_markdown(contributions)

    updated = (
        content[:start]
        + "\n\n"
        + generated
        + "\n\n"
        + content[end:]
    )

    README.write_text(
        updated,
        encoding="utf-8"
    )

    print("=" * 50)
    print("Open Source Contributions Updated")
    print("=" * 50)
    print(f"Qualifying contributions: {len(contributions)}")
    print(f"Minimum repository stars: {MIN_STARS + 1}")
    print(f"Maximum displayed: {MAX_CONTRIBUTIONS}")
    print("=" * 50)


if __name__ == "__main__":
    update_readme()
