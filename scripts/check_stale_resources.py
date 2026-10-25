
"""Mark GitHub resources stale based on their last push date."""

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json

from resources.resource_utils import (
    CSV_PATH,
    COL_LINK,
    COL_STALE,
    N_COLS,
    read_lines,
    split_eol,
    serialize_row,
    write_lines,
)


def github_repo(link):
    """Return owner/repo from a GitHub URL, or None."""
    parsed = urlparse(link.strip())
    if parsed.hostname not in {"github.com", "www.github.com"}:
        return None
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2 or parts[0] in {".", ".."}:
        return None
    owner, repo = parts[:2]
    if repo in {".", ".."}:
        return None
    if repo.endswith(".git"):
        repo = repo[:-4]
    return f"{owner}/{repo}"


def get_pushed_at(repo, token=None):
    """Fetch a repository's last-push timestamp."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "awesome-claude-code-stale-check",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com/repos/{repo}", headers=headers)
    with urlopen(request, timeout=15) as response:
        data = json.load(response)
    return datetime.fromisoformat(data["pushed_at"].replace("Z", "+00:00"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=CSV_PATH)
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.days < 1:
        parser.error("--days must be at least 1")

    lines = read_lines(args.csv)
    if not lines:
        parser.error("CSV is empty")

    import csv
    header, _ = split_eol(lines[0])
    headers = next(csv.reader([header]))
    if len(headers) != N_COLS or "Link" not in headers or "Stale" not in headers:
        parser.error("Unexpected CSV schema")

    link_col = headers.index("Link")
    stale_col = headers.index("Stale")
    now = datetime.now(timezone.utc)
    token = os.environ.get("GITHUB_TOKEN")
    changes = 0
    checked = 0

    for index in range(1, len(lines)):
        content, eol = split_eol(lines[index])
        if not content.strip():
            continue
        try:
            fields = next(csv.reader([content]))
        except csv.Error as error:
            print(f"SKIP CSV line {index + 1}: {error}")
            continue
        if len(fields) != N_COLS:
            print(f"SKIP CSV line {index + 1}: unexpected column count")
            continue

        repo = github_repo(fields[link_col])
        if not repo:
            continue
        try:
            pushed_at = get_pushed_at(repo, token)
        except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as error:
            print(f"SKIP {repo}: unable to check ({error})")
            continue

        checked += 1
        stale = (now - pushed_at).days >= args.days
        value = "TRUE" if stale else "FALSE"
        if fields[stale_col].strip().upper() != value:
            print(f"{value}: {repo} (last push: {pushed_at.date()})")
            if not args.dry_run:
                fields[stale_col] = value
                lines[index] = serialize_row(fields, eol)
            changes += 1

    print(f"Checked {checked} GitHub repositories; {changes} flag(s) would change.")
    if args.dry_run:
        print("Dry run: CSV not modified.")
    elif changes:
        write_lines(lines, args.csv)
        print(f"Updated {args.csv}")
    else:
        print("No CSV changes needed.")


if __name__ == "__main__":
    main()
