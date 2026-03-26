# Permits Tab Rebuild — Pete 2.0 (Revised)

## What You Asked For

1. Strip the current Permits tab — no jurisdiction rules table, no stats cards. Default state: **"No permits requested yet."**
2. When a permit comes through, automatically start the research/processing
3. Conversational interface **inside JT** so the team can work with the system directly on the Permits tab
4. Access restricted to Notification Members ONLY (8 people)
5. All automated output goes to **#test-job-materials** for now (same test-mode pattern as JT Trigger Flow)

---

## What Gets Removed

Everything currently on the Permits tab:

- 4 hero stat cards (Total Permits, Approved, Pending, AI Verified)
- Permit Documents list
- Jurisdiction Rules table (286 rules — stays in the database as AI context, just not displayed)
- The "0/0 APPROVED" badge

Replaced with a clean empty state: **"No permits requested yet."**

---

## What Gets Built

### Part 1: Clean Slate + Auto-Trigger

**Permits Tab UI (PermitsTab.tsx) — Empty State**

- Default view: centered message — "No permits requested yet."
- No stats, no tables, no cards — just the message until a permit packet exists for this job

**Permits Tab UI — Active State (when permit packet exists)**

Two sections stacked:

1. **Permit Checklist** — AI-generated steps to complete (from research). Each step shows:
   - Step number + action description
   - Phone number / website (clickable)
   - Estimated fee
   - Checkbox — who completed it, when (logged)
   - Notes field per step (who wrote it, when)
   - Status indicator (pending / done)

2. **Chat with Pete** — A chat interface at the bottom of the tab (like a built-in assistant). Team members type questions, Pete responds with permit knowledge about this specific job. Chat history persists per job.

**Auto-Trigger (n8n workflow)**

When an install job is sold (detected by JT Trigger Flow which already fires on new jobs), if the job is install-track (BU contains "Replacement" or "Whole House"):

1. Look up customer city from `st_locations_v2`
2. Call Claude API with web search to research permit requirements for that city + job type
3. Save the research result (steps, contacts, fees, gotchas, confidence) to `permit_packets` table
4. Post a notification to **#test-job-materials** (`C0AJ3AWJWH5`): "📋 Permit research complete for Job #{jobNumber} — {city}. {X} steps identified."
5. The Permits tab picks it up automatically on next page load — switches from empty state to active state

**All output to #test-job-materials until you flip to production** — same pattern as JT Trigger Flow's `PRODUCTION_MODE` flag.

**New table: `spartan_ops.permit_packets`**

| Column | Type | Purpose |
|--------|------|---------|
| id | SERIAL | PK |
| st_job_id | BIGINT | FK to job |
| st_location_id | BIGINT | Location lookup |
| customer_city | TEXT | City for research |
| customer_state | TEXT | State |
| job_types | TEXT[] | What work is being done |
| research | JSONB | AI research result (steps, contacts, fees, gotchas) |
| checked_steps | JSONB | Who completed each step (user_id, user_name, timestamp) |
| notes | JSONB | Per-step notes from team |
| general_notes | JSONB | Overall job permit notes |
| status | TEXT | Researching / Ready / InProgress / Filed / Pending / Approved / OnSite |
| confidence | TEXT | high / medium / low |
| created_at | TIMESTAMP | When research was triggered |
| updated_at | TIMESTAMP | Last interaction |

**New table: `spartan_ops.permit_chat`**

| Column | Type | Purpose |
|--------|------|---------|
| id | SERIAL | PK |
| st_job_id | BIGINT | FK to job |
| role | TEXT | 'user' or 'assistant' |
| message | TEXT | The message content |
| user_id | TEXT | Slack user ID of sender (null for assistant) |
| user_name | TEXT | Display name |
| created_at | TIMESTAMP | When sent |

---

### Part 2: Chat with Pete (In-JT Conversational Interface)

**How it works:** At the bottom of the Permits tab, there's a chat input. The team member types a question about permits for this job. The frontend calls a new API endpoint which:

1. Validates the user is a Notification Member (by Slack user ID from their JT session)
2. Loads the job's permit research context + jurisdiction rules + chat history
3. Sends to Claude API with the full context
4. Saves both the question and response to `permit_chat`
5. Returns the response to display in the chat UI

**New API endpoint: `/api/job/[jobNumber]/permit-chat`**

- **POST** — Send a message, get AI response
  - Request: `{ message: string }`
  - Validates sender is Notification Member
  - Returns: `{ response: string, chatHistory: [...] }`
- **GET** — Load chat history for this job
  - Returns: `{ messages: [...] }`

**What Pete knows in context:**
- This job's permit research (steps, contacts, fees, gotchas)
- The 286 jurisdiction rules from `permit_rules` table (as background knowledge)
- Pete's original jurisdiction data (Dayton area cities — phone numbers, addresses, websites)
- The chat history for this job
- The job's details (customer, address, city, job type)

**Example interactions:**
- "Do we need a permit for this?" → AI checks job type against rules and research
- "What's the building department number?" → Pulls from research
- "Inspector said we need a separate gas permit" → AI responds and can note it
- "How much is the permit fee?" → Pulls from research
- "What about Centerville — do they require a separate tap permit?" → AI researches if needed

**Chat UI Design (inside Permits tab):**
- Glass card at the bottom of the tab
- Message bubbles — user messages right-aligned, Pete responses left-aligned
- Each message shows sender name + timestamp
- Input field with send button
- Loading state while AI responds
- Auto-scrolls to newest message
- Matches the Glass Command Center dark theme

---

### Part 3: Checklist Interactions (In-JT)

**New API endpoint: `/api/job/[jobNumber]/permit-action`**

- **POST** — Toggle step, save note, update status
  - Request: `{ action: 'toggleStep' | 'saveNote' | 'updateStatus', stepNum?: number, value?: string }`
  - Validates sender is Notification Member
  - Updates `permit_packets` (checked_steps, notes, status)
  - Returns updated state

All write actions (checking steps, adding notes, changing status, sending chat messages) are **gated by Notification Members check**. Read-only viewing of permit status stays available to anyone with JT access.

---

### Part 4: Access Control

**Who gets access to interact:** Only the 8 Notification Members.

Read from the Notification_Members tab of the Spartan Database Google Sheet (`1t_RpnVX6i88qk52xdd1wnOcZzBOCLn-FTWqwAcNMk6w`) — or cached in the existing hardcoded list for speed:

| Slack User ID | Notes |
|---------------|-------|
| U06N32PKK8U | Member |
| U06MN0CHE3G | Josh Ferguson |
| U06NHDPGRA4 | Member |
| U07U4RCJX9B | Member |
| U06NAXE0M3S | Member |
| U06N3S2B4GW | Member |
| U06NKNW6CDT | Member |
| U06NT7YQR6X | Member |

**Where enforced:**
- `/api/job/[jobNumber]/permit-chat` — POST requires Notification Member
- `/api/job/[jobNumber]/permit-action` — POST requires Notification Member
- In the UI: chat input and step checkboxes are **hidden** for non-members (they see the permit status read-only but can't interact)

**How user identity is determined:** The JT app already has Slack OAuth. The logged-in user's Slack ID is available from the session. The API endpoints check this against the member list.

---

## What Stays vs. What Goes

| Current | Decision |
|---------|----------|
| `permit_rules` table (286 rows) | **Stays** in DB — used as AI context, not shown on tab |
| `permit_documents` table (287 rows) | **Stays** for now — new system uses `permit_packets` instead |
| Permit Document Ingestion workflow | **Keep running** for now — doesn't conflict. Deactivate later |
| Jurisdiction Rules table on UI | **Removed** from tab |
| 4 stat cards on UI | **Removed** |
| JT API route permit data | **Modified** — also returns `permit_packets` + `permit_chat` |

---

## Build Order

| Step | What | Effort |
|------|------|--------|
| 1 | Create `permit_packets` + `permit_chat` tables | 15 min |
| 2 | Rewrite `PermitsTab.tsx` — empty state + checklist + chat UI | 2-3 hours |
| 3 | Build `/api/job/[jobNumber]/permit-chat` endpoint | 1-2 hours |
| 4 | Build `/api/job/[jobNumber]/permit-action` endpoint | 1 hour |
| 5 | Update JT API route to serve permit_packets data | 30 min |
| 6 | Add Notification Members access check to both endpoints | 30 min |
| 7 | Build auto-trigger n8n workflow (job sold → AI research → save → post to #test-job-materials) | 2-3 hours |
| 8 | Test with a real install job | 30 min |

**Total estimate: 8-10 hours across sessions**

---

## Summary

- **Tab is clean** — "No permits requested yet" until there's actually a permit
- **Automatic** — sell an install job, AI researches permits, checklist appears on the tab
- **Chat with Pete lives inside JT** — no Slack back-and-forth, team works directly on the Permits tab
- **All automated notifications go to #test-job-materials** — nothing hits real channels until you approve
- **Locked down** — only 8 Notification Members can interact (chat, check steps, add notes). Everyone else sees read-only status
- **No new infrastructure** — runs on existing JT app + n8n + Supabase