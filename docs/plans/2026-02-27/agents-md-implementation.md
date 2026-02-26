# AGENTS.md Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a comprehensive development guide for AI agents in the panager repository.

**Architecture:** A single Markdown file in the project root containing structured development workflows, testing commands, and coding standards.

**Tech Stack:** Markdown, Python (for command reference), ruff.

---

### Task 1: Create AGENTS.md with Overview and Setup

**Files:**
- Create: `/Users/johjun/Documents/plugagent.click/plugagent_lab/panager/AGENTS.md`

**Step 1: Write the initial content**
Write the first 40 lines covering the project index, repository structure, and environment setup (.env.example).

**Step 2: Commit**
```bash
git add AGENTS.md
git commit -m "docs: AGENTS.md 개요 및 환경 설정 섹션 추가"
```

### Task 2: Add Core Commands and Testing Workflow

**Files:**
- Modify: `/Users/johjun/Documents/plugagent.click/plugagent_lab/panager/AGENTS.md`

**Step 1: Append Command and Testing section**
Add sections for `make` commands, detailed `pytest` (single test) instructions, and Discord direct testing with log checking.

**Step 2: Commit**
```bash
git add AGENTS.md
git commit -m "docs: AGENTS.md 핵심 명령어 및 테스트 워크플로우 추가"
```

### Task 3: Add Coding Standards and Tool Development Guide

**Files:**
- Modify: `/Users/johjun/Documents/plugagent.click/plugagent_lab/panager/AGENTS.md`

**Step 1: Append Coding Standards**
Add `from __future__ import annotations` requirement, `ruff` formatting, Tool development rules (JSON return), and Error handling.

**Step 2: Commit**
```bash
git add AGENTS.md
git commit -m "docs: AGENTS.md 코딩 규약 및 도구 개발 가이드 추가"
```

### Task 4: Add Git Workflow and State Management

**Files:**
- Modify: `/Users/johjun/Documents/plugagent.click/plugagent_lab/panager/AGENTS.md`

**Step 1: Append Git and State sections**
Add Conventional Commits (Korean) and LangGraph `AgentState` management tips.

**Step 2: Final Verification**
Check total lines (approx. 150) and formatting.

**Step 3: Commit**
```bash
git add AGENTS.md
git commit -m "docs: AGENTS.md 워크플로우 마무리 및 최종 업데이트"
```
