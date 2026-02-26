# Coding Standards and Tool Development Guide Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Append coding standards and tool development guidelines to `AGENTS.md` to ensure high-quality, consistent code from AI agents.

**Architecture:** Update documentation only.

**Tech Stack:** Markdown.

---

### Task 1: Append Coding Standards and Tool Development Guide

**Files:**
- Modify: `/Users/johjun/Documents/plugagent.click/plugagent_lab/panager/AGENTS.md`

**Step 1: Append the new sections**

Append the following content to the end of `AGENTS.md`:

```markdown

---

## 📜 Coding Standards & Tool Development

### 🐍 Python & Style
- **Imports**: Always include `from __future__ import annotations` at the top of every Python file for postponed evaluation of annotations.
- **Formatting**: Use `ruff` for linting and formatting. Adhere to the project's \`.ruff.toml\` if present.
- **Naming**:
  - \`snake_case\` for variables, functions, and modules.
  - \`PascalCase\` for classes.
  - Constants should be \`UPPER_SNAKE_CASE\`.
- **Types**: Mandatory type annotations for all function signatures and complex variables. Use \`| None\` for optional types (e.g., \`str | None\`) rather than \`Optional[str]\`.

### 🛠 Tool Development (CRITICAL)
- **Location**: Place all new tools in \`src/panager/tools/\` using domain-specific filenames (e.g., \`google.py\`, \`github.py\`).
- **Decorator**: Every tool must be decorated with \`@tool\` from \`langchain_core.tools\`.
- **Return Type**: **MANDATORY**: Every tool MUST return a **JSON-formatted string**. Do not return raw objects, dictionaries, or plain text unless it's strictly required by the caller. This ensures compatibility with the agent's observation handling.
- **Documentation**: Provide clear, descriptive docstrings for every tool, explaining parameters and return values.

### 🛡 Error Handling & Logging
- **Exceptions**: Use specialized exception classes defined in \`src/panager/core/exceptions.py\`.
- **Logging**: Use the project-wide logger. Avoid \`print()\` statements; use \`logger.info()\`, \`logger.error()\`, etc., to provide visibility into agent execution.
```

**Step 2: Commit changes**

Run:
```bash
git add AGENTS.md
git commit -m "docs: AGENTS.md 코딩 규약 및 도구 개발 가이드 추가"
```
