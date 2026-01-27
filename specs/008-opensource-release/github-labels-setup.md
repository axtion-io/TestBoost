# GitHub Labels Setup (T023)

This document provides instructions for setting up GitHub labels manually or via API.

## Labels to Create

Create the following labels in the GitHub repository settings:

| Label | Color | Description |
|-------|-------|-------------|
| `good first issue` | `#7057ff` (green) | Good for newcomers - easy tasks to get started |
| `help wanted` | `#008672` (blue) | Community contributions welcome |
| `documentation` | `#0075ca` (light blue) | Documentation improvements |
| `bug` | `#d73a4a` (red) | Something isn't working |
| `enhancement` | `#a2eeef` (purple) | New feature or request |
| `question` | `#d876e3` (yellow) | Further information is requested |

## Method 1: Via GitHub UI (Recommended)

1. Go to https://github.com/cheche71/TestBoost/labels
2. Click "New label" for each label above
3. Enter the label name, description, and color
4. Click "Create label"

## Method 2: Via GitHub CLI

If you have `gh` CLI installed:

```bash
# Install gh CLI if needed
# https://cli.github.com/

# Authenticate
gh auth login

# Create labels
gh label create "good first issue" --color "7057ff" --description "Good for newcomers" --repo cheche71/TestBoost
gh label create "help wanted" --color "008672" --description "Community contributions welcome" --repo cheche71/TestBoost
gh label create "documentation" --color "0075ca" --description "Documentation improvements" --repo cheche71/TestBoost
gh label create "bug" --color "d73a4a" --description "Something isn't working" --repo cheche71/TestBoost
gh label create "enhancement" --color "a2eeef" --description "New feature or request" --repo cheche71/TestBoost
gh label create "question" --color "d876e3" --description "Further information is requested" --repo cheche71/TestBoost
```

## Method 3: Via GitHub API

Using curl:

```bash
GITHUB_TOKEN="your_token_here"
REPO="cheche71/TestBoost"

# good first issue
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$REPO/labels \
  -d '{"name":"good first issue","color":"7057ff","description":"Good for newcomers"}'

# help wanted
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$REPO/labels \
  -d '{"name":"help wanted","color":"008672","description":"Community contributions welcome"}'

# documentation
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$REPO/labels \
  -d '{"name":"documentation","color":"0075ca","description":"Documentation improvements"}'

# bug
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$REPO/labels \
  -d '{"name":"bug","color":"d73a4a","description":"Something isn'\''t working"}'

# enhancement
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$REPO/labels \
  -d '{"name":"enhancement","color":"a2eeef","description":"New feature or request"}'

# question
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$REPO/labels \
  -d '{"name":"question","color":"d876e3","description":"Further information is requested"}'
```

## After Creating Labels

1. **Apply to existing issues**: Go through existing issues and apply relevant labels
2. **Add at least 3 "good first issue" tags**: Identify 3-5 beginner-friendly issues and tag them
3. **Update issue templates**: Ensure templates reference these labels

## Verification

Check that all labels appear at: https://github.com/cheche71/TestBoost/labels

---

**Task**: T023 [P2] [US2]
**Status**: Manual action required (GitHub access needed)
**Date**: 2026-01-26
