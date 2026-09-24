# Release Notes Runbook

Each formal SurgePilot release has one authoritative user-facing notes file at
`docs/releases/vX.Y.Z.md`. The filename must exactly match the formal Git tag. The formal
release workflow reads that file directly and publishes it as the GitHub Release body; generated
notes and manually entered release text are not parallel sources.

## Required format

Write release notes in English for release users, not as a raw commit list. Use these headings:

```markdown
## Highlights

## Install

## Upgrade

## Compatibility and breaking changes

## Full changelog
```

Do not add a top-level release title to the notes body. GitHub renders the separately configured
`SurgePilot vX.Y.Z` Release title above the body, while the exact version remains authoritative in
the `docs/releases/vX.Y.Z.md` filename.

Under those headings:

- explain the user-visible changes and link the relevant pull requests or documentation;
- include the supported installation command;
- state whether an upgrade is required and give the applicable manual guidance;
- state compatibility changes and breaking changes explicitly, using `None` when there are none;
- link to the GitHub comparison for incremental releases, or the tagged commit history for the
  first release.

Do not claim verification, compatibility, migrations, or features that are not supported by the
tagged source, governing design, tests, and release evidence.

## Author and review

The version-preparation change must add or update `docs/releases/vX.Y.Z.md` before publication.
Review the notes with the version change and compare them against the previous tag,
merged pull requests, user documentation, compatibility matrix, and any installation or manual
version-transition changes.

After the version-preparation PR is merged, start the `Release` workflow on `main` through the
Actions tab or `gh workflow run release.yml --ref main`. The workflow requires the selected commit
to remain the current `main` commit, derives the exact target tag from root `VERSION`, and runs the
full candidate build and smoke checks before it creates the formal tag. Do not create or push the
formal tag manually. A failed pre-tag candidate can be rerun; a failure after tag creation follows
the create-only new-version recovery rule.

The release workflow checks the exact versioned file during preflight and again immediately before
staging the draft. `scripts/validate_release_notes.py` requires the exact tag-matched filename, no
top-level title, the five headings above in order, and substantive non-comment content in every
section. A missing or invalid file blocks publication before the GitHub Release or semantic image
tags are created. The draft is created with `--notes-file`, so the reviewed file is the published
body.

## Historical metadata correction

A release-body correction is metadata-only. Before editing an existing body, record the tag target
and every asset ID, name, size, and digest. Update the body from the matching checked-in notes file
with `gh release edit <tag> --notes-file docs/releases/<tag>.md`, then confirm the tag target and
asset inventory are unchanged. Never upload, replace, rename, or delete assets as part of a notes
correction.

The formal workflow remains create-only. Historical body corrections are exceptional maintenance;
they do not permit moving tags, changing release identity, replacing artifacts, or resuming a
failed same-version publication.
