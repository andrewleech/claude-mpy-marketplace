---
---

# MicroPython PR Workflow

## PR Description Guidelines

### Style
* The title should focus on the end user effect of the change, prefixed with the component: `stm32: Add DMA support for SPI.`
* All PR/MR descriptions should be written succinctly with a casual / personal writing style with minimal extra sub-headings if any.
* Do NOT list commits or provide checklists of things done/not-done.
* Provide only brief detail and background, we can assume everyone reading this is already a micropython expert.
* Use regular dashes (-), not em dashes.
* Do not hard-wrap paragraphs; let the renderer handle line wrapping.

### Template

Before writing a PR description, verify the template below still matches the upstream PR template at:
`micropython/.github/pull_request_template.md`
(or fetch it with `gh api repos/micropython/micropython/contents/.github/pull_request_template.md --jq '.content' | base64 -d`)

If the upstream template has changed, flag this to the user before proceeding.

Use this template for PR descriptions:

``` markdown
### Summary

<!-- Explain the reason for making this change. What problem does the pull request
     solve, or what improvement does it add? Add links if relevant,
     especially links to open issues. -->

### Testing

<!-- Explain what testing you did, and on which boards/ports. If there are
     boards or ports that you couldn't test, please mention this here as well.

     If you leave this section empty then your Pull Request may be closed. -->

### Trade-offs and Alternatives

<!-- If the Pull Request has some negative impact (i.e. increased code size)
     then please explain why you think the trade-off improvement is worth it.
     If you can think of alternative ways to do this, please explain that here too.

     Delete this heading if not relevant (i.e. small fixes) -->

### Generative AI

I used generative AI tools when creating this PR, but a human has checked the
code and is responsible for the code and the description above.
```

Notes on filling in the template:
* **Summary** should open with the user-facing feature or problem in plain English. Technical implementation detail can follow but keep it brief -- the code speaks for itself.
* **Testing** must not be left empty or the PR may be closed. Name specific boards/ports tested and mention any that were not tested.
* **Trade-offs** -- delete this section entirely for small fixes. Only include it when there's a genuine trade-off to explain.
* **Generative AI** -- keep the single applicable statement. Delete the one that doesn't apply. The upstream template provides two options; we always use the "I used generative AI" one.

## GitHub PR Guidelines
* The upstream repo https://github.com/micropython/micropython should always be used for PR's.
* Git pushes should always go to the origin or andrewleech remote.

## Private Review Workflow (Preferred)
Draft PRs on the GitHub fork (andrewleech/micropython) are used for pre-submission review. This gives full CI coverage during review via GitHub Actions, unlike the previous GitLab workflow where CI only ran after the public PR was raised.

An ephemeral integration branch is used as the PR base instead of master to avoid any risk of accidentally modifying master on the fork.

**Process:**
1. Make changes and create commits with sign-off: `git commit -s`
2. Push feature branch to origin: `git push origin feature-branch`
3. Create an ephemeral base branch from upstream master:
   ```bash
   git fetch upstream
   git push origin upstream/master:refs/heads/review/feature-branch
   ```
4. Create draft PR on the fork:
   ```bash
   gh pr create --repo andrewleech/micropython --draft \
     --base review/feature-branch \
     --head feature-branch \
     --title "component: Brief description with end user focus" \
     --body "$(cat <<'EOF'
   [Use PR description template above]
   EOF
   )"
   ```
5. Review in GitHub web UI (code, description, CI results)
6. Iterate on changes as needed:
   - Make code changes and update PR description if needed
   - Amend commits: `git commit --amend` or new commits
   - Force push updates: `git push origin feature-branch --force`
   - CI re-runs automatically; `concurrency` + `cancel-in-progress` in workflow YAMLs cancels stale runs
   - **After rebasing onto upstream/master**, update the ephemeral base branch too:
     `git push origin upstream/master:refs/heads/review/feature-branch --force`
     Otherwise the PR diff will include upstream commits that aren't part of the feature branch
7. When satisfied, close the draft PR (don't merge):
   `gh pr close <number> --repo andrewleech/micropython`
8. Delete the ephemeral base branch:
   `git push origin --delete review/feature-branch`
9. Create public PR on upstream:
   ```bash
   gh pr create --repo micropython/micropython \
     --base master \
     --head andrewleech:feature-branch \
     --title "component: Brief description" \
     --body "$(cat <<'EOF'
   [Use PR description template above]
   EOF
   )"
   ```

**Key points:**
- Use `--draft` flag to prevent accidental merge on the fork
- Force pushing the feature branch during review is expected
- The `review/*` branch is ephemeral -- create one per feature, delete after closing the draft PR
- Never push to origin/master directly -- sync via `git fetch upstream && git push origin upstream/master:master`
- The `push:` trigger in workflow YAMLs means every push to origin triggers CI; this is fine for a public fork (free Actions minutes) and cancel-in-progress handles churn
- PR description is part of the review and may be iterated

## Commit History Requirements

MicroPython does not squash-merge PRs. The commit tree submitted is the commit tree that lands on master. Every PR must have a clean, logical commit history ready for rebase or merge.

* **No broad "fixup" commits.** Never address review feedback by adding a catch-all commit like "fix review comments" or "address feedback" at HEAD. Each fix must be folded back into the commit it logically belongs to (via `git rebase -i`, `git commit --fixup` + `git rebase --autosquash`, [`git autosquash`](http://github.com/andrewleech/git-autosquash), or `jj absorb`).
* **Each commit should be a self-contained, reviewable unit.** A reviewer reading any single commit should see a coherent change, not a partial change that only makes sense after a later fixup.
* **Force-pushing rewritten history is expected** during review on feature branches. This is normal workflow, not something to avoid.
* **Commit messages must use imperative mood** and be prefixed with the relevant component, matching the PR title style (e.g. `stm32: Add DMA support for SPI.`).
* **All commits must include `Signed-off-by`** via `git commit -s`.

## Working with PRs via gh
The `gh` tool can be used to interact with Pull Requests:
* List PRs: `gh pr list`
* View PR details: `gh pr view <PR_NUMBER>`
* View PR comments: `gh pr view <PR_NUMBER> --comments`
* View PR diff: `gh pr diff <PR_NUMBER>`
* Check out a PR: `gh pr checkout <PR_NUMBER>`

The GitHub API can also be accessed directly:
```bash
# Get review comments on a PR (inline on code)
gh api -H "Accept: application/vnd.github+json" \
       -H "X-GitHub-Api-Version: 2022-11-28" \
       /repos/micropython/micropython/pulls/<PR_NUMBER>/comments

# Get PR issue comments (main discussion)
gh api -H "Accept: application/vnd.github+json" \
       -H "X-GitHub-Api-Version: 2022-11-28" \
       /repos/micropython/micropython/issues/<PR_NUMBER>/comments

# Get PR review status
gh api -H "Accept: application/vnd.github+json" \
       -H "X-GitHub-Api-Version: 2022-11-28" \
       /repos/micropython/micropython/pulls/<PR_NUMBER>/reviews
```
