
from pathlib import Path


def update_readme(contributions):

    readme_path = Path("README.md")

    start_marker = "<!-- OPEN_SOURCE_CONTRIBUTIONS:START -->"
    end_marker = "<!-- OPEN_SOURCE_CONTRIBUTIONS:END -->"

    readme = readme_path.read_text(encoding="utf-8")

    if start_marker not in readme or end_marker not in readme:
        raise ValueError(
            "Open source contribution markers not found in README.md"
        )

    start = readme.index(start_marker) + len(start_marker)
    end = readme.index(end_marker, start)

    if start > end:
        raise ValueError("Invalid contribution marker order.")

    generated_html = generate_markdown(contributions)

    updated_readme = (
        readme[:start]
        + "\n\n"
        + generated_html
        + "\n\n"
        + readme[end:]
    )

    if updated_readme == readme:
        print("README is already up to date.")
        return

    readme_path.write_text(
        updated_readme,
        encoding="utf-8"
    )

    print(
        f"README successfully updated with "
        f"{len(contributions)} contributions."
    )



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
        repo = html.escape(item["repo"])

        repo_url = html.escape(
            item["repo_url"], quote=True
        )

        pr_url = html.escape(
            item["url"], quote=True
        )

        language = html.escape(item["language"])
        category = html.escape(item["category"])

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
        '<table align="center" width="100%" cellpadding="12" cellspacing="0">\n'
        + "\n".join(rows)
        + "\n</table>"
    )
update_readme(contributions)
