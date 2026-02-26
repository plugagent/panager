# Design: AGENTS.md (Development Workflow Focus)

## Overview
The goal of this task is to create a comprehensive `AGENTS.md` file (approximately 150 lines) that serves as the primary development guide for AI agents operating in the **panager** repository. The file will emphasize practical development workflows, coding standards, and testing procedures.

## Core Sections

### 1. Project Index & Structure
- Summarize the tech stack: Python 3.13, `uv`, LangGraph, PostgreSQL (`pgvector`).
- Provide a clear directory map highlighting the roles of `src/panager/agent`, `tools`, `services`, and `integrations`.

### 2. Setup & Environment
- Detail the environment configuration process:
    - Copy `.env.example` to `.env`.
    - Configure key variables (`DISCORD_TOKEN`, `OPENAI_API_KEY`, etc.).
- List essential development commands:
    - `make dev`: Hot-reload development.
    - `make db`: Start local PostgreSQL.
    - `make migrate-test`: Apply database migrations.

### 3. Testing & Verification
- Comprehensive `pytest` usage:
    - Running all tests: `make test`.
    - Running a single file: `POSTGRES_HOST=localhost POSTGRES_PORT=5432 uv run pytest <path> -v`.
    - Running a single test: `... uv run pytest <path>::<test_name> -v`.
- **Discord Direct Testing**: Instructions for running the bot and interacting via Discord, including handling OAuth buttons and checking `logs/panager.log`.

### 4. Development Workflow (Mandatory)
- **Code Style**:
    - `from __future__ import annotations` must be the first line of every file.
    - Strict adherence to `ruff` for linting and formatting.
    - Type annotations are required (prefer `X | None`).
- **Tool Development**:
    - Location: `src/panager/tools/<domain>.py`.
    - Decoration: Use `@tool` with descriptive docstrings for semantic indexing.
    - **Return Requirement**: Tools MUST return structured JSON strings for reliable LLM parsing.
- **Service Layer**: Decouple business logic into `src/panager/services/`.
- **Error Handling**: Use `panager.core.exceptions` and define domain-specific errors.

### 5. Git & Workflow Completion
- **Commit Messages**: Follow Conventional Commits with **Korean** descriptions in the body (e.g., `feat: Add Google Calendar integration (구글 캘린더 연동 추가)`).
- **State Management**: Guidelines on using `AgentState` within LangGraph nodes and maintaining conversation context via `thread_id`.

## Implementation Strategy
- Read existing configuration and files to ensure accuracy (already performed).
- Write the final `AGENTS.md` to the project root.
- Validate the file length and content against the requirements.
