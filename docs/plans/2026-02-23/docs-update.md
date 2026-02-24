# Docs Update Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create README.md and update AGENTS.md to reflect new project features and deployment structure.

**Architecture:** Documentation update.

**Tech Stack:** Markdown.

---

### Task 1: Create README.md

**Files:**
- Create: `README.md`

**Step 1: Write README.md with requested content**

Content to include:
- Project Name: panager (Discord DM Personal Manager)
- Core Features: 날짜 지능화(내일/모레/글피), 에이전트 재진입 기반 도구 예약 실행, 장기 메모리(MemoryService).
- Tech Stack: Python 3.13, `uv`, LangGraph, PostgreSQL (pgvector), Cloudflare Zero-Trust.
- Deployment: GitHub Actions + GHCR + Cloudflare SSH Tunneling.

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README.md 신규 생성"
```

### Task 2: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

**Step 1: Add "JSON-First Tool Response" section**

Add after "Imports" or in "Code Style" section.
Description: All tool responses must return structured JSON using `json.dumps`.

**Step 2: Update "Production Commands"**

Replace existing "Production" section (lines 59-64) with GitHub Actions CD description.

**Step 3: Update "Key Architectural Notes"**

Add technical explanation for agent re-entry (`trigger_task`) and `AgentState` flag (`is_system_trigger`).

**Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs: AGENTS.md 최신화 (JSON 응답 규칙, CD 방식 및 재진입 아키텍처 추가)"
```

### Task 3: Final Verification

**Step 1: Verify file contents**

Run `cat README.md` and `cat AGENTS.md` to ensure correct formatting and content.

**Step 2: Commit all (if any remaining)**

The user requested a specific final commit message: `docs: README 생성 및 AGENTS.md 최신화 (CI/CD 및 신규 기능 반영)`. I will use this for the final combined commit or as the last commit if I do them separately. Actually, the user asked to do `git add` and commit *after* finishing. So I should probably do one big commit at the end.

---
**Combined Commit Message:**
`docs: README 생성 및 AGENTS.md 최신화 (CI/CD 및 신규 기능 반영)`
