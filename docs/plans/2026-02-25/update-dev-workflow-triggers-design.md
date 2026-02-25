# Design Document: Update Dev Workflow Triggers

## Overview
This document describes the changes to the `.github/workflows/dev.yml` file to optimize CI/CD pipeline execution by ignoring changes to documentation, local development configurations, and IDE-specific files.

## Problem Statement
Currently, the `dev.yml` workflow triggers on every push to the `dev` branch. This leads to unnecessary resource consumption and deployment cycles when only non-functional files (like documentation or local dev tools) are modified.

## Proposed Changes
Modify the `on: push` section of `.github/workflows/dev.yml` to include a `paths-ignore` list.

### Exclusion Patterns
- `docs/**`: Project-specific documentation.
- `**/*.md`: All Markdown files (README, AGENTS, codemap, etc.).
- `.vscode/**`, `.idea/**`: IDE-specific settings.
- `.python-version`: Local Python version management.
- `.gitignore`, `.dockerignore`: Git and Docker metadata.
- `.env.example`: Environment variable templates.
- `Makefile`: Local task automation.
- `docker-compose.dev.yml`, `docker-compose.test.yml`: Local orchestration files.

## Architecture & Data Flow
No changes to the actual jobs or deployment logic. The change is strictly at the GitHub Actions trigger level.

## Testing Plan
1. Push changes to `dev.yml` to the `dev` branch (this push itself will trigger the workflow).
2. Create a test commit modifying only a `.md` file on the `dev` branch and verify that the workflow does NOT trigger.
3. Create a test commit modifying a source file (e.g., `src/panager/main.py`) and verify that the workflow DOES trigger.
