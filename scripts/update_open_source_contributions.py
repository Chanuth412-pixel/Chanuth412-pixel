
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
<td>

<strong>
<a href="{pr_url}">{title}</a>
</strong>

<br/>

<a href="{repo_url}">
<strong>{repo}</strong>
</a>

<br/><br/>

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
        '<table align="center" width="100%">\n'
        + "\n".join(rows)
        + "\n</table>"
    )
