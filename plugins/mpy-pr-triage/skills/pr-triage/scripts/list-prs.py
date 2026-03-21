#!/usr/bin/env python3
"""List open MicroPython PRs with branch names, external feedback, and worktree status.

Usage:
    list-prs.py [--repo OWNER/REPO] [--author AUTHOR] [--sort newest|oldest|feedback]
                [--local-repo PATH] [--limit N]

Defaults:
    --repo micropython/micropython
    --author andrewleech
    --sort feedback  (most recent external feedback first)
    --local-repo .   (current directory, for worktree detection)
    --limit 100
"""

import argparse
import json
import os
import subprocess
import sys


def run_gh(args):
    """Run a gh CLI command and return parsed JSON."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"gh error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout) if result.stdout.strip() else []


def get_worktrees(repo_path):
    """Get set of branch names that have active worktrees."""
    result = subprocess.run(
        ["git", "-C", repo_path, "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}

    worktrees = {}
    current_path = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):]
        elif line.startswith("branch refs/heads/"):
            branch = line[len("branch refs/heads/"):]
            if current_path:
                worktrees[branch] = current_path
    return worktrees


def get_local_branches(repo_path):
    """Get set of all local branch names."""
    result = subprocess.run(
        ["git", "-C", repo_path, "branch", "--format=%(refname:short)"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    return set(line.strip() for line in result.stdout.splitlines() if line.strip())


def main():
    parser = argparse.ArgumentParser(description="List open MicroPython PRs")
    parser.add_argument("--repo", default="micropython/micropython")
    parser.add_argument("--author", default="andrewleech")
    parser.add_argument(
        "--sort",
        choices=["newest", "oldest", "feedback"],
        default="feedback",
    )
    parser.add_argument("--local-repo", default=".")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    # Resolve repo path
    repo_path = os.path.abspath(args.local_repo)

    # Fetch PRs
    fields = "number,title,updatedAt,createdAt,headRefName,comments,reviews,isDraft,labels,url"
    prs = run_gh([
        "pr", "list",
        "--repo", args.repo,
        "--author", args.author,
        "--state", "open",
        "--json", fields,
        "--limit", str(args.limit),
    ])

    # Get local git info
    worktrees = get_worktrees(repo_path)
    local_branches = get_local_branches(repo_path)

    # Process each PR
    enriched = []
    for pr in prs:
        branch = pr.get("headRefName", "")
        # Strip author prefix if present (e.g. andrewleech:branch -> branch)
        if ":" in branch:
            branch = branch.split(":", 1)[1]

        # Find latest external feedback
        latest_feedback_ts = None
        latest_feedback_author = None
        bot_authors = {"codecov", "codecov-commenter", "github-actions"}

        for c in pr.get("comments", []):
            author = c.get("author", {}).get("login", "")
            if author != args.author and author not in bot_authors:
                ts = c.get("createdAt", "")
                if latest_feedback_ts is None or ts > latest_feedback_ts:
                    latest_feedback_ts = ts
                    latest_feedback_author = author

        for r in pr.get("reviews", []):
            author = r.get("author", {}).get("login", "")
            if author != args.author and author not in bot_authors:
                ts = r.get("submittedAt", "") or r.get("createdAt", "")
                if ts and (latest_feedback_ts is None or ts > latest_feedback_ts):
                    latest_feedback_ts = ts
                    latest_feedback_author = author

        # Worktree / branch status
        wt_path = worktrees.get(branch)
        has_local_branch = branch in local_branches

        entry = {
            "number": pr["number"],
            "title": pr["title"],
            "branch": branch,
            "url": pr.get("url", ""),
            "created": pr["createdAt"][:10],
            "updated": pr["updatedAt"][:10],
            "is_draft": pr.get("isDraft", False),
            "labels": [l.get("name", "") for l in pr.get("labels", [])],
            "feedback_date": latest_feedback_ts[:10] if latest_feedback_ts else None,
            "feedback_author": latest_feedback_author,
            "has_local_branch": has_local_branch,
            "worktree_path": wt_path,
        }
        enriched.append(entry)

    # Sort
    if args.sort == "feedback":
        enriched.sort(
            key=lambda e: (e["feedback_date"] or "0000-00-00"),
            reverse=True,
        )
    elif args.sort == "newest":
        enriched.sort(key=lambda e: e["created"], reverse=True)
    elif args.sort == "oldest":
        enriched.sort(key=lambda e: e["created"])

    if args.json:
        json.dump(enriched, sys.stdout, indent=2)
        print()
        return

    # Table output
    # Split into groups: with feedback and without
    with_feedback = [e for e in enriched if e["feedback_date"]]
    no_feedback = [e for e in enriched if not e["feedback_date"]]

    def print_row(e):
        wt_indicator = ""
        if e["worktree_path"]:
            wt_indicator = f" [wt: {e['worktree_path']}]"
        elif e["has_local_branch"]:
            wt_indicator = " [local]"

        draft = " (draft)" if e["is_draft"] else ""
        feedback = ""
        if e["feedback_date"]:
            feedback = f" | feedback: {e['feedback_date']} by {e['feedback_author']}"

        print(
            f"#{e['number']:5d} | {e['branch']:45s} | {e['created']}"
            f"{feedback}{draft}{wt_indicator}"
        )
        print(f"        {e['title']}")

    if with_feedback:
        print(f"=== PRs with external feedback ({len(with_feedback)}) ===")
        print()
        for e in with_feedback:
            print_row(e)
            print()

    if no_feedback:
        print(f"=== PRs without external feedback ({len(no_feedback)}) ===")
        print()
        for e in no_feedback:
            print_row(e)
            print()

    print(f"Total: {len(enriched)} open PRs ({len(with_feedback)} with feedback, {len(no_feedback)} without)")


if __name__ == "__main__":
    main()
