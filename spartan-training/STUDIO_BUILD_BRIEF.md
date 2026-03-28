# Spartan Studio — Claude Code Build Brief

> Drop this file in your repo root or feed it to Claude Code as context.
> Branch `feat/spartan-studio` already exists with page wrapper stubs.

---

## STEP 0: READ THE DESIGN SYSTEM FIRST

Before writing ANY code, read these files and match their patterns exactly:
- `src/app/globals.css` — CSS vars, fonts, component classes
- `src/components/AppShell.tsx` — nav pattern, header, layout
- `src/app/page.tsx` — page pattern, card usage, inline styles

**Design DNA:**
- Fonts: `Archivo Black` (logo/hero headings), `Barlow Condensed` (nav, labels, section headers), `Barlow` (body), `JetBrains Mono` (code/monospace)
- Colors: `--bg: #0a0a0a`, `--bg2: #111`, `--bg3: #1a1a1a`, `--bg4: #222`, `--gold: #c8a84e`, `--gold2: #e0c060`, `--green: #3ecf8e`, `--red: #b91c1c`, `--blue: #3b82f6`, `--text: #e8e8e8`, `--text2: #999`, `--text3: #555`, `--border: #222`
- Components: `.card`, `.btn`, `.btn-gold`, `.btn-outline`, `.badge`, `.badge-gold`, `.badge-green`, `.badge-blue`
- All components use inline styles (not className for layout), same as AppShell.tsx and page.tsx patterns
- Dark theme everywhere. No white backgrounds anywhere.
- Nav uses `Barlow Condensed`, uppercase, letter-spacing 1, font-weight 600/700

**HARD GATE: This must look professionally designed. Match the existing aesthetic exactly. No generic AI look.**

---

## WHAT TO BUILD (Phase A)

### Files to CREATE:

1. **`src/components/studio/StudioHome.tsx`** — Studio landing page (tool launcher)
2. **`src/components/studio/ScriptGenerator.tsx`** — AI script generation tool
3. **`src/components/studio/Teleprompter.tsx`** — Full-screen teleprompter
4. **`src/app/studio/page.tsx`** — Already exists on branch (imports StudioHome)
5. **`src/app/studio/scripts/page.tsx`** — Already exists on branch (imports ScriptGenerator)
6. **`src/app/studio/prompter/page.tsx`** — Already exists on branch (imports Teleprompter)
7. **`src/app/api/studio/scripts/route.ts`** — Claude API proxy for script generation
8. **`src/app/api/studio/cards/route.ts`** — Fetches all SOP cards for the picker

### Files to UPDATE:

9. **`src/components/AppShell.tsx`** — Add "Studio" to NAV array (adminOnly: true, href: "/studio"), widen main maxWidth when pathname starts with "/studio" (use 1200 instead of 960)
10. **`src/middleware.ts`** — `/studio` and `/api/studio` routes need admin role check (same pattern as `/admin` check already there)

---

## COMPONENT SPECS

### StudioHome.tsx

Tool launcher grid. Two sections: "Available Now" and "Coming Soon".

**Available Now (2 tools):**
- Script Generator — href: /studio/scripts, accent: #c8a84e
- Teleprompter — href: /studio/prompter, accent: #3ecf8e

**Coming Soon (5 tools, greyed out at 50% opacity):**
- Screenshot & Annotate — accent: #3b82f6
- Image Editor — accent: #e0c060
- Screen Recorder — accent: #ef4444
- Video Trimmer — accent: #a855f7
- Brand Assets — accent: #f59e0b

**Layout:**
- Hero section with Archivo Black "STUDIO" heading + subtle gold radial gradient background glow
- Subtitle in Barlow: "Create scripts, record walkthroughs, edit graphics, and build training content without leaving Academy."
- Available tools as large interactive cards (hover: border changes to accent color, slight translateY(-2px), box shadow)
- Each tool card: icon (SVG, 56x56 container) + name (Barlow Condensed, uppercase) + description (Barlow, --text3) + "Open Tool >" CTA
- Coming Soon: smaller cards, same layout but 50% opacity, no hover/click

### ScriptGenerator.tsx

Two-panel layout. Left panel (400px): input controls. Right panel (flex 1): script output.

**Left Panel:**
- Mode toggle tabs at top: "From SOP Card" | "Custom Content" (gold bottom border on active)
- SOP Card mode: searchable dropdown of all 282 cards. Fetch from `/api/studio/cards`. Show title + board/library path. Preview card content snippet when selected.
- Custom mode: textarea for freeform content
- Tone selector: three options as radio-style buttons
  - "Walk & Talk" — casual field training vibe
  - "Professional" — polished, clear
  - "Quick Tip" — 60-second punch
- Generate button (btn-gold style, full width, disabled when no content selected)
- Loading state: spinner + "Generating Script..."

**Right Panel:**
- Empty state: centered icon + "No Script Yet" message
- Generated state:
  - Header bar with word count badge, read time badge
  - Copy button (btn-outline)
  - "Teleprompter" button (btn-gold) — saves script to sessionStorage key `studio_prompter_script`, navigates to /studio/prompter
  - Editable textarea showing the generated script (transparent bg, no border, Barlow font, 15px, line-height 1.8)

**Back button** in header — arrow icon in bordered circle, links back to /studio

### Teleprompter.tsx

**Two states:**

**No Script Loaded:**
- Centered empty state with icon
- "Open Script Generator" button (btn-gold)
- "Paste Script" button (btn-outline) — opens textarea to paste
- Keyboard shortcuts reference card at bottom

**Script Loaded (the actual teleprompter):**
- Black background (#000), full viewport height
- Script text scrolls vertically
- Section headers (lines starting with ## or all-caps lines) rendered in Barlow Condensed, gold color, larger font
- Regular text in Barlow, #e8e8e8

**Visual elements:**
- Center line guide: subtle horizontal band with gold border-top/bottom at ~35% from top
- Top fade: gradient from #000 to transparent (top 20%)
- Bottom fade: gradient from transparent to #000 (bottom 25%)
- Controls bar at bottom with gradient background

**Controls bar (bottom):**
- Left: "Change Script" button, Restart button (circular arrow icon)
- Center: Speed down (-), speed display (JetBrains Mono, e.g. "2.0x"), Speed up (+), Play/Pause button (large 52px gold circle), "5s Start" countdown button
- Right: Font size A-/A+ buttons with size display, Mirror toggle, Fullscreen toggle

**Features:**
- Play/pause: `requestAnimationFrame` scroll loop, speed = `speed * 30` pixels per second
- Speed: 0.5x to 8x in 0.5 increments
- Font size: 20px to 72px in 4px steps
- Mirror mode: CSS `transform: scaleX(-1)` on scroll container
- Fullscreen: Fullscreen API
- 5-second countdown: overlay with large gold number (Archivo Black, 120px), "GET READY" subtitle
- Auto-hide controls after 3s during playback in fullscreen, show on mouse move
- Auto-stop when scrolled to bottom
- Keyboard: Space=play/pause, Up/Down=speed, R=restart, Esc=exit fullscreen

**Loads script from:** `sessionStorage.getItem("studio_prompter_script")` on mount (set by Script Generator)

---

## API ROUTES

### `/api/studio/scripts/route.ts`

POST endpoint. Admin-only (check x-user-role header from middleware).

**Request body:** `{ content: string, tone: "casual" | "professional" | "quicktip", title?: string }`

**Implementation:**
- Requires `ANTHROPIC_API_KEY` env var (return 500 with clear error if missing)
- Calls `https://api.anthropic.com/v1/messages` with:
  - model: `claude-sonnet-4-20250514`
  - max_tokens: 2000
  - Headers: `x-api-key`, `anthropic-version: 2023-06-01`
- System prompt tells Claude to write as a script writer for Spartan Plumbing training videos. Josh Ferguson is the speaker. Casual walk-and-talk style. No stage directions. Use ## headers for sections. Include "common mistake" callouts. End with recap.
- Tone-specific instructions in the system prompt based on the `tone` parameter
- Extract text from response content blocks, return as `{ script: string }`

### `/api/studio/cards/route.ts`

GET endpoint. Admin-only.

**Implementation:**
```typescript
import { query } from "@/lib/supabase";
```

Query:
```sql
SELECT c.id, c.title, c.content, b.name as board_name, l.name as library_name
FROM knowledge_lake.sop_cards c
JOIN knowledge_lake.sop_playbooks p ON p.id = c.playbook_id
JOIN knowledge_lake.sop_libraries l ON l.id = p.library_id
JOIN knowledge_lake.sop_boards b ON b.id = l.board_id
ORDER BY b.sort_order, l.sort_order, p.sort_order, c.sort_order
```

Return flat array. Use `export const dynamic = "force-dynamic"`.

---

## APPSHELL CHANGES

In the NAV array, add:
```typescript
{ href: "/studio", label: "Studio", adminOnly: true },
```

In the `isActive` function, add:
```typescript
if (href === "/studio") return pathname.startsWith("/studio");
```

In the `<main>` tag, change maxWidth to be dynamic:
```typescript
maxWidth: pathname.startsWith("/studio") ? 1200 : 960,
```

---

## MIDDLEWARE CHANGES

In the admin-only route check, add `/studio` and `/api/studio`:
```typescript
if (pathname.startsWith("/admin") || pathname.startsWith("/api/admin") || pathname.startsWith("/studio") || pathname.startsWith("/api/studio")) {
  if (payload.role !== "admin") {
    return NextResponse.redirect(new URL("/", request.url));
  }
}
```

---

## KEY TECHNICAL NOTES

- Supabase queries use `query()` from `@/lib/supabase` — returns FLAT ARRAY, not `{rows: [...]}`. Never use `.rows`.
- App uses `exec_sql` RPC function (not `run_sql`)
- JWT auth via `jose` library, cookie name `spartan_session`
- Middleware injects `x-user-id`, `x-user-email`, `x-user-role` headers
- All pages that fetch data need `export const dynamic = "force-dynamic"`
- Next.js 15.1, React 19, TypeScript, Tailwind 3
- The page wrapper files on the branch are minimal — just import and render the component

---

## ENV VAR NEEDED

Add to Vercel (Settings > Environment Variables):
```
ANTHROPIC_API_KEY = sk-ant-...
```

Without this, the Script Generator will return a clear error message but won't crash.

---

## AFTER BUILD

1. Run `npm run build` to verify no TypeScript errors
2. Test each route: /studio, /studio/scripts, /studio/prompter
3. Create PR from `feat/spartan-studio` to `main`
4. Verify Vercel preview deployment works
