#!/usr/bin/env python3
"""Post a GitHub PR review from structured JSON findings.

Accepts validated review findings as JSON (stdin or file) and posts a
GitHub PR review with summary body and inline comments. Designed to be
called by review agents via Bash tool.

Exit codes:
  0  Success (JSON result on stdout)
  1  Input validation error (JSON error on stdout, message on stderr)
  2  GitHub API error (JSON error on stdout, message on stderr)
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_ALLOWED_COMMENT_FIELDS = {"path", "body", "line", "side", "start_line", "start_side"}


def _error(code: int, error_type: str, message: str) -> None:
    """Print structured error JSON to stdout and human message to stderr, then exit."""
    json.dump({"error": error_type, "message": message}, sys.stdout)
    sys.stdout.write("\n")
    print(message, file=sys.stderr)
    sys.exit(code)


def _resolve_token(token: str | None, token_file: str | None) -> str:
    """Resolve GitHub token from args or environment."""
    if token_file:
        try:
            with open(token_file) as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError) as e:
            _error(1, "token_error", f"Cannot read token file {token_file}: {e}")
    if token:
        return token
    env_token = os.environ.get("GITHUB_TOKEN")
    if env_token:
        return env_token
    _error(1, "auth_missing", "No GitHub token provided. Use --token, --token-file, or GITHUB_TOKEN env var.")
    return ""  # unreachable


def _github_api(method: str, path: str, token: str, payload: dict | None = None):
    """Make a GitHub API request."""
    url = f"https://api.github.com{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 204:
                return {}
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = ""
        if e.fp:
            try:
                error_body = e.fp.read().decode("utf-8")[:500]
            except Exception:
                pass
        raise RuntimeError(f"HTTP {e.code}: {error_body or e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}") from e


def parse_diff_ranges(diff_text: str) -> dict[str, list[tuple[int, int]]]:
    """Parse a unified diff to extract valid new-file line ranges per file.

    Returns {filepath: [(start, end), ...]} where start/end are inclusive
    new-file line numbers that appear in the diff.
    """
    ranges: dict[str, list[tuple[int, int]]] = {}
    current_file = None

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("+++ /dev/null"):
            current_file = None
        elif current_file and (m := _HUNK_RE.match(line)):
            start = int(m.group(2))
            count = int(m.group(3)) if m.group(3) else 1
            end = start + count - 1 if count > 0 else start
            ranges.setdefault(current_file, []).append((start, end))

    return ranges


def validate_line_ranges(findings: list[dict], diff_ranges: dict[str, list[tuple[int, int]]]) -> list[dict]:
    """Validate finding line numbers against diff ranges. Returns list of errors."""
    errors = []
    for f in findings:
        file_path = f.get("file", "")
        line = f.get("line")
        if not file_path or line is None:
            continue

        file_ranges = diff_ranges.get(file_path)
        if file_ranges is None:
            errors.append({
                "error": "file_not_in_diff",
                "file": file_path,
                "line": line,
                "message": f"file {file_path} not found in diff",
            })
            continue

        in_range = any(start <= line <= end for start, end in file_ranges)
        if not in_range:
            flat_ranges = [f"{s}-{e}" for s, e in file_ranges]
            errors.append({
                "error": "line_out_of_range",
                "file": file_path,
                "line": line,
                "valid_ranges": flat_ranges,
                "message": f"line {line} outside diff range for {file_path}, valid ranges: {', '.join(flat_ranges)}",
            })

    return errors


def build_review_body(summary: str, findings: list[dict]) -> str:
    """Build the review summary body text."""
    severity_counts: dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    parts = [summary]
    if severity_counts:
        counts_str = ", ".join(f"{count} {sev}" for sev, count in sorted(severity_counts.items()))
        parts.append(f"\n**Findings:** {counts_str}")

    return "\n".join(parts)


def build_comments(findings: list[dict]) -> list[dict]:
    """Convert findings to GitHub review comment format."""
    comments = []
    for f in findings:
        status = f.get("status", "KEEP")
        body = f.get("body") or f.get("description", "")
        title = f.get("title", "")
        severity = f.get("severity", "")
        recommendation = f.get("recommendation", "")

        # Build comment body
        parts = []
        if severity:
            parts.append(f"**[{severity}]** {title}" if title else f"**[{severity}]**")
        elif title:
            parts.append(f"**{title}**")

        if status == "QUESTIONABLE":
            parts.insert(0, "[Questionable]")

        if body:
            parts.append(body)
        if recommendation:
            parts.append(f"\n**Recommendation:** {recommendation}")

        comment = {
            "path": f.get("file", ""),
            "body": "\n\n".join(parts),
            "line": f.get("line", 1),
            "side": f.get("side", "RIGHT"),
        }
        # Strip any fields GitHub API won't accept
        comment = {k: v for k, v in comment.items() if k in _ALLOWED_COMMENT_FIELDS}
        comments.append(comment)

    return comments


def delete_pending_reviews(owner: str, repo: str, pr_number: int, token: str) -> None:
    """Delete stale PENDING reviews left by previous attempts."""
    try:
        reviews = _github_api("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews", token)
        for rev in reviews:
            if rev.get("state") == "PENDING":
                _github_api("DELETE", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews/{rev['id']}", token)
                print(f"Deleted stale pending review {rev['id']}", file=sys.stderr)
    except RuntimeError as e:
        print(f"Warning: failed to clean pending reviews: {e}", file=sys.stderr)


def post_review(
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
    comments: list[dict],
    token: str,
    commit_sha: str | None = None,
) -> dict:
    """Post a GitHub PR review. Returns result dict."""
    delete_pending_reviews(owner, repo, pr_number, token)

    payload: dict = {
        "body": body,
        "event": "COMMENT",
    }
    if commit_sha:
        payload["commit_id"] = commit_sha
    if comments:
        payload["comments"] = comments

    try:
        result = _github_api("POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews", token, payload)
        return {
            "review_id": result.get("id"),
            "comment_count": len(comments),
            "rejected_comments": [],
        }
    except RuntimeError as e:
        error_str = str(e)
        # 422 with thread errors means comments target lines outside the diff
        if "422" in error_str and comments and "pull_request_review_thread" in error_str.lower():
            print(f"Warning: {len(comments)} comments rejected, retrying body-only", file=sys.stderr)
            payload.pop("comments", None)
            try:
                result = _github_api("POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews", token, payload)
                return {
                    "review_id": result.get("id"),
                    "comment_count": 0,
                    "rejected_comments": len(comments),
                    "note": "All inline comments rejected (lines outside diff). Review posted with summary only.",
                }
            except RuntimeError as retry_err:
                _error(2, "api_error", f"Retry failed: {retry_err}")

        _error(2, "api_error", str(e))
    return {}  # unreachable


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Post a GitHub PR review from structured JSON findings.",
        epilog="Reads findings JSON from --findings file or stdin.",
    )
    parser.add_argument("--repo", required=True, help="GitHub repository slug (owner/name)")
    parser.add_argument("--pr", required=True, type=int, help="PR number")
    parser.add_argument("--findings", help="Path to JSON findings file (default: stdin)")
    parser.add_argument("--diff", help="Path to diff file for line range validation")
    parser.add_argument("--token-file", help="Path to file containing GitHub token")
    parser.add_argument("--token", help="GitHub token (prefer --token-file or GITHUB_TOKEN env)")
    parser.add_argument("--head-sha", help="Pin review to specific commit SHA")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be posted without posting")
    args = parser.parse_args()

    # Parse repo slug
    repo_parts = args.repo.split("/")
    if len(repo_parts) != 2:
        _error(1, "invalid_repo", f"Invalid repo format: {args.repo}. Expected owner/name.")
    owner, repo = repo_parts

    # Read findings JSON
    if args.findings:
        try:
            with open(args.findings) as f:
                input_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            _error(1, "invalid_input", f"Cannot read findings file: {e}")
    else:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            _error(1, "invalid_input", f"Invalid JSON on stdin: {e}")

    # Validate input structure
    if not isinstance(input_data, dict):
        _error(1, "invalid_input", "Input must be a JSON object with 'summary' and 'findings' fields")

    summary = input_data.get("summary", "")
    findings = input_data.get("findings", [])
    if not isinstance(findings, list):
        _error(1, "invalid_input", "'findings' must be a JSON array")

    # Filter to KEEP and QUESTIONABLE only
    active_findings = [f for f in findings if f.get("status", "KEEP") != "INVALID"]

    # Validate line ranges if diff provided
    if args.diff:
        try:
            with open(args.diff) as f:
                diff_text = f.read()
        except FileNotFoundError:
            _error(1, "diff_not_found", f"Diff file not found: {args.diff}")

        diff_ranges = parse_diff_ranges(diff_text)
        line_errors = validate_line_ranges(active_findings, diff_ranges)
        if line_errors:
            json.dump({"error": "line_validation_failed", "details": line_errors}, sys.stdout)
            sys.stdout.write("\n")
            for err in line_errors:
                print(err["message"], file=sys.stderr)
            sys.exit(1)

    # Build review
    review_body = build_review_body(summary, active_findings)
    comments = build_comments(active_findings)

    if args.dry_run:
        output = {
            "dry_run": True,
            "repo": args.repo,
            "pr": args.pr,
            "body": review_body,
            "comment_count": len(comments),
            "comments": comments,
        }
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(0)

    # Resolve auth
    token = _resolve_token(args.token, args.token_file)

    # Post
    result = post_review(owner, repo, args.pr, review_body, comments, token, args.head_sha)
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
