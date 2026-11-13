
import os
import sys
import json
import html
import urllib.request
import urllib.error

from pathlib import Path
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

GITHUB_USERNAME = os.getenv(
    "GITHUB_USERNAME", "Chanuth412-pixel"
)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

MIN_STARS = 500
MAX_CONTRIBUTIONS = 8
RESULTS_PER_PAGE = 100
MAX_SEARCH_RESULTS = 1000

START_MARKER = "<!-- OPEN_SOURCE_CONTRIBUTIONS:START -->"
END_MARKER = "<!-- OPEN_SOURCE_CONTRIBUTIONS:END -->"

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

README_PATH = (
    Path(__file__).resolve().parent.parent / "README.md"
)


# ============================================================
# GITHUB GRAPHQL API
# ============================================================

GRAPHQL_QUERY = """
query($searchQuery: String!, $cursor: String) {
  search(
    query: $searchQuery
    type: ISSUE
    first: 100
    after: $cursor
  ) {
    issueCount

    pageInfo {
      hasNextPage
      endCursor
    }

    nodes {
      ... on PullRequest {
        title
        number
        url
        mergedAt

        labels(first: 20) {
          nodes {
            name
          }
        }

        repository {
          nameWithOwner
          url
          stargazerCount
          forkCount
          isPrivate

          owner {
            login
          }

          primaryLanguage {
            name
          }
        }
      }
    }
  }
}
"""


def github_graphql(token, query, variables):
    """Execute a GitHub GraphQL API request."""

    payload = json.dumps({
        "query": query,
        "variables": variables
    }).encode("utf-8")

    request = urllib.request.Request(
        GITHUB_GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=30
        ) as response:
            result = json.loads(response.read())

    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API HTTP error {error.code}: {details}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not connect to GitHub API: {error}"
        ) from error

    if result.get("errors"):
        raise RuntimeError(
            f"GitHub GraphQL error: {result['errors']}"
        )

    return result["data"]


# ============================================================
# CATEGORY CLASSIFICATION
# ============================================================

def classify_category(title, labels):
    """Assign a short contribution category without using PR descriptions."""

    title_lower = title.lower()

    label_names = [
        label.lower() for label in labels
    ]

    text = " ".join(label_names + [title_lower])

    if any(word in text for word in [
        "documentation",
        "docs",
        "tutorial",
        "readme",
        "typo"
    ]):
        return "Documentation"

    if any(word in text for word in [
        "bug",
        "bugfix",
        "bug fix",
        "fix"
    ]):
        return "Bug Fix"

    if any(word in text for word in [
        "test",
        "testing",
        "coverage"
    ]):
        return "Testing"

    if any(word in text for word in [
        "feature",
        "enhancement",
        "implement"
    ]):
        return "Feature"

    if any(word in text for word in [
        "refactor",
        "cleanup",
        "maintenance"
    ]):
        return "Code Improvement"

    return "Open Source"


# ============================================================
# FETCH MERGED CONTRIBUTIONS
# ============================================================

def fetch_contributions(token, username):
    """
    Fetch merged PRs authored by the user.

    Filters:
      - External repositories only.
      - Public repositories only.
      - More than 500 stars.
      - Merged PRs only.
    """

    search_query = (
        f"author:{username} "
        "is:pr is:merged "
        "sort:updated-desc"
    )

    cursor = None
    candidates = []
    total_results = None

    print("Searching GitHub for merged pull requests...")

    while True:

        result = github_graphql(
            token,
            GRAPHQL_QUERY,
            {
                "searchQuery": search_query,
                "cursor": cursor
            }
        )

        search = result["search"]

        if total_results is None:
            total_results = search["issueCount"]

            print(
                f"GitHub returned {total_results} "
                "matching merged pull requests."
            )

            if total_results > MAX_SEARCH_RESULTS:
                print(
                    "Warning: GitHub search is limited "
                    "to the first 1000 matching results."
                )

        nodes = search["nodes"]

        for pr in nodes:

            if not pr:
                continue

            repository = pr.get("repository")

            if not repository:
                continue

            # Ensure the PR is actually merged.
            merged_at = pr.get("mergedAt")

            if not merged_at:
                continue

            # Exclude private repositories.
            if repository.get("isPrivate"):
                continue

            # Exclude repositories owned by the user.
            owner = repository["owner"]["login"]

            if owner.lower() == username.lower():
                continue

            # Only repositories with MORE than 500 stars.
            stars = repository.get("stargazerCount", 0)

            if stars <= MIN_STARS:
                continue

            labels = [
                label["name"]
                for label in pr["labels"]["nodes"]
            ]

            language_data = repository.get(
                "primaryLanguage"
            )

            language = (
                language_data["name"]
                if language_data
                else "Other"
            )

            contribution = {
                "title": pr["title"],
                "repo": repository["nameWithOwner"],
                "repo_url": repository["url"],
                "url": pr["url"],
                "language": language,
                "category": classify_category(
                    pr["title"], labels
                ),
                "stars": stars,
                "forks": repository["forkCount"],
                "merged_at": merged_at,
                "number": pr["number"]
            }

            candidates.append(contribution)

        page_info = search["pageInfo"]

        if not page_info["hasNextPage"]:
            break

        if len(candidates) >= MAX_SEARCH_RESULTS:
            break

        cursor = page_info["endCursor"]

    # Sort by actual merge date, newest first.
    candidates.sort(
        key=lambda item: item["merged_at"],
        reverse=True
    )

    # Remove duplicate PR entries.
    unique = {}

    for item in candidates:
        unique[item["url"]] = item

    contributions = list(unique.values())

    # Display only the latest qualifying contributions.
    contributions = contributions[:MAX_CONTRIBUTIONS]

    print(
        f"Found {len(contributions)} qualifying "
        "external contributions."
    )

    return contributions


# ============================================================
# FORMATTING HELPERS
# ============================================================

def format_count(number):

    number = int(number or 0)

    if number >= 1000000:
        return f"{number / 1000000:.1f}M".replace(".0M", "M")

    if number >= 1000:
        return f"{number / 1000:.1f}k".replace(".0k", "k")

    return str(number)


def format_date(value):

    if not value:
        return "Date unavailable"

    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).strftime("%d %b %Y")


# ============================================================
# GENERATE CONTRIBUTION HTML
# ============================================================

def generate_markdown(contributions):

    if not contributions:
        return (
            "<p align='center'>"
            "<i>No qualifying merged contributions found yet.</i>"
            "</p>"
        )

    rows = []

    for item in contributions:

        title = html.escape(str(item["title"]))
        repo = html.escape(str(item["repo"]))

        repo_url = html.escape(
            str(item["repo_url"]), quote=True
        )

        pr_url = html.escape(
            str(item["url"]), quote=True
        )

        language = html.escape(str(item["language"]))
        category = html.escape(str(item["category"]))

        stars = format_count(item["stars"])
        forks = format_count(item["forks"])

        date = format_date(item["merged_at"])

        rows.append(f"""
<tr>
<td align="left">

<strong>
<a href="{pr_url}">{title}</a>
</strong>

<br/>

<a href="{repo_url}"><strong>{repo}</strong></a>

<br/>

⭐ {stars} stars
&nbsp; · &nbsp;
🍴 {forks} forks
&nbsp; · &nbsp;
<code>{language}</code>

<br/><br/>

<sub>
{category}
&nbsp; · &nbsp;
PR #{item["number"]}
&nbsp; · &nbsp;
Merged {date}
</sub>

</td>
</tr>
""")

    return (
        '<table align="center" width="100%" '
        'cellpadding="12" cellspacing="0">\n'
        + "\n".join(rows)
        + "\n</table>"
    )


# ============================================================
# UPDATE README
# ============================================================

def update_readme(contributions):

    if not README_PATH.exists():
        raise FileNotFoundError(
            f"README not found: {README_PATH}"
        )

    readme = README_PATH.read_text(
        encoding="utf-8"
    )

    # Ensure markers exist exactly once.
    if readme.count(START_MARKER) != 1:
        raise ValueError(
            "Expected exactly one START marker in README.md"
        )

    if readme.count(END_MARKER) != 1:
        raise ValueError(
            "Expected exactly one END marker in README.md"
        )

    start = readme.index(START_MARKER)
    end = readme.index(END_MARKER)

    if start >= end:
        raise ValueError(
            "Invalid contribution marker order."
        )

    # Generate contribution HTML.
    generated_html = generate_markdown(
        contributions
    )

    # Preserve markers and replace only their contents.
    content_start = start + len(START_MARKER)

    updated_readme = (
        readme[:content_start]
        + "\n\n"
        + generated_html
        + "\n\n"
        + readme[end:]
    )

    if updated_readme == readme:
        print("README is already up to date.")
        return

    README_PATH.write_text(
        updated_readme,
        encoding="utf-8"
    )

    print(
        f"README successfully updated with "
        f"{len(contributions)} contributions."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not GITHUB_TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN environment variable is missing."
        )

    if not GITHUB_USERNAME:
        raise RuntimeError(
            "GITHUB_USERNAME environment variable is missing."
        )

    print("=" * 55)
    print("OPEN SOURCE CONTRIBUTION UPDATER")
    print("=" * 55)

    contributions = fetch_contributions(
        GITHUB_TOKEN,
        GITHUB_USERNAME
    )

    update_readme(contributions)

    print("=" * 55)
    print("Contribution update completed.")
    print("=" * 55)


if __name__ == "__main__":

    try:
        main()

    except Exception as error:
        print(
            f"ERROR: {error}",
            file=sys.stderr
        )
        sys.exit(1)
