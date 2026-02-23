# Tailscale CD Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transition the CD pipeline from Cloudflare Tunnel to Tailscale for more reliable and secure deployments.

**Architecture:** Use Tailscale's overlay network to establish a direct, encrypted connection between GitHub Actions runners and the target server, bypassing public internet exposure and complex proxy handshakes.

**Tech Stack:** Tailscale, GitHub Actions, Docker Compose, SSH.

---

### Task 1: Server-Side Tailscale SSH Setup

**Files:**
- Modify: (System Command)

**Step 1: Enable Tailscale SSH on the target server**
Run (on server): `sudo tailscale up --ssh --accept-routes --reset`
Expected: Server restarts Tailscale with SSH feature enabled.

**Step 2: Verify Tailscale IP**
Run (on server): `tailscale ip -4`
Expected: Output starting with `100.`

**Step 3: Test local SSH via Tailscale IP**
Run (from another Tailscale device): `ssh <user>@100.x.y.z`
Expected: Successful login without manual password (if Tailscale SSH is configured) or with existing keys.

### Task 2: Tailscale ACL & OAuth Verification

**Files:**
- Modify: Tailscale Admin Console (Manual)

**Step 1: Configure ACL for the CD tag**
Ensure `tag:panager-cd` exists and has access to the server on port 22 in the Tailscale ACL editor.
Expected: `{"action": "accept", "src": ["tag:panager-cd"], "dst": ["<server-ip>:22"]}` is present.

**Step 2: Verify OAuth Client**
Ensure the OAuth client has `devices:read` and `auth_keys:write` scopes and is associated with `tag:panager-cd`.

### Task 3: GitHub Secrets Verification

**Files:**
- Modify: GitHub Repository Settings (Manual)

**Step 1: Check required secrets**
Verify `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET`, and `SERVER_TS_IP` are registered in GitHub Secrets.

### Task 4: Trigger and Verify CD Pipeline

**Files:**
- Modify: `.github/workflows/cd.yml` (already modified, but trigger needed)

**Step 1: Push changes to main**
Run: `git add .github/workflows/cd.yml && git commit -m "feat: migrate CD to Tailscale" && git push origin main`
Expected: GitHub Action starts.

**Step 2: Monitor "Connect to Tailscale" step**
Expected: Step completes within 10-20 seconds with "Success" and assigns the `panager-cd` tag.

**Step 3: Monitor "Deploy" step**
Expected: SSH connection succeeds via `100.x.y.z` and `docker compose up -d` completes.

**Step 4: Verify application status on server**
Run (on server): `docker compose ps`
Expected: `panager` service is `running`.
