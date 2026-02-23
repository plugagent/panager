# Codemap Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate comprehensive codemap.md files for all major modules and a Root Atlas for the repository.

**Architecture:** Systematic documentation of responsibility, design, flow, and integration for each directory using the cartography skill framework.

**Tech Stack:** Markdown, Cartography skill (scripts/cartographer.py)

---

### Task 1: Create Core and API Codemaps

**Files:**
- Create: `src/panager/core/codemap.md`
- Create: `src/panager/api/codemap.md`

**Step 1: Write src/panager/core/codemap.md**
(Content detailing Responsibility, Design, Flow, Integration for core)

**Step 2: Write src/panager/api/codemap.md**
(Content detailing Responsibility, Design, Flow, Integration for api)

**Step 3: Commit**
`git add src/panager/core/codemap.md src/panager/api/codemap.md`
`git commit -m "docs: core 및 api 모듈 코드맵 추가"`

### Task 2: Create DB and Integrations Codemaps

**Files:**
- Create: `src/panager/db/codemap.md`
- Create: `src/panager/integrations/codemap.md`

**Step 1: Write src/panager/db/codemap.md**
(Content for db)

**Step 2: Write src/panager/integrations/codemap.md**
(Content for integrations)

**Step 3: Commit**
`git add src/panager/db/codemap.md src/panager/integrations/codemap.md`
`git commit -m "docs: db 및 integrations 모듈 코드맵 추가"`

### Task 3: Create Agent, Services, and Discord Codemaps

**Files:**
- Create: `src/panager/agent/codemap.md`
- Create: `src/panager/services/codemap.md`
- Create: `src/panager/discord/codemap.md`

**Step 1: Write src/panager/agent/codemap.md**
(Content for agent)

**Step 2: Write src/panager/services/codemap.md**
(Content for services)

**Step 3: Write src/panager/discord/codemap.md**
(Content for discord)

**Step 4: Commit**
`git add src/panager/agent/codemap.md src/panager/services/codemap.md src/panager/discord/codemap.md`
`git commit -m "docs: agent, services, discord 모듈 코드맵 추가"`

### Task 4: Create Root Package and Root Atlas Codemaps

**Files:**
- Create: `src/panager/codemap.md`
- Create: `codemap.md` (Root Atlas)

**Step 1: Write src/panager/codemap.md**
(Content for package root)

**Step 2: Write codemap.md**
(Content for Repository Atlas)

**Step 3: Commit**
`git add src/panager/codemap.md codemap.md`
`git commit -m "docs: 루트 패키지 및 저장소 전체 아틀라스 추가"`

### Task 5: Update Cartography State

**Step 1: Update state**
Run: `python3 ~/.config/opencode/skills/cartography/scripts/cartographer.py update --root ./`

**Step 2: Commit**
`git add .slim/cartography.json`
`git commit -m "docs: 코드맵 상태 업데이트"`
