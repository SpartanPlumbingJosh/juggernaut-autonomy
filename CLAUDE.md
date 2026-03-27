# CLAUDE.md - Juggernaut Project Context

## What This Is

Spartan Plumbing LLC (Dayton, OH) internal ops platform. The primary deliverable is **Spartan Job Tracker (JT)** - a Next.js app at `jt.spartan-plumbing.com`.

## Repo Structure

- `spartan-jt/` - The Job Tracker (Next.js 15, React 19, Tailwind CSS). This is the main thing being actively developed.
- `mcp/` - Juggernaut MCP server (Railway)
- `n8n-workflows/` - Workflow exports
- Everything else (agents, orchestrator, dashboard, etc.) is legacy/secondary

## JT Architecture

- 13-tab job lifecycle dashboard pulling from Supabase
- Vercel deployment: auto-deploys on push to `main` via PR
- Supabase backend: `spartan_ops` schema, all ST tables use `_v2` suffix
- External Supabase URL: `https://kong.thejuggernaut.org/rest/v1/rpc/run_sql`
- Requires `Content-Profile: spartan_ops` header + CF-Access headers for external calls

## Development Rules

### Git Workflow (MANDATORY)
1. Never push directly to `main` - branch protection is enforced
2. Create a feature branch, make changes, run `cd spartan-jt && npm run build`
3. Push branch, open PR
4. CI runs "Build spartan-jt" check - must pass
5. CodeRabbit reviews, auto-merge fires on approval + passing checks

### Code Rules
- Always run `npm run build` in `spartan-jt/` before committing
- Fix ALL TypeScript errors before pushing
- No `any` types unless absolutely necessary
- Keep components in `spartan-jt/src/`

### Supabase Column Gotchas
- `st_calls.st_job_id` is TEXT, all other tables use BIGINT - explicit casting for joins
- `st_jobs_v2` has no `track_type` - derive from `st_business_unit_id` JOIN to `st_business_units`
- `st_jobs_v2` has no `business_unit_name` - JOIN to `st_business_units`
- Invoice `total` includes tax - use `subtotal` for revenue
- Estimate/invoice/PO items are JSONB in parent tables, not separate tables

### n8n Rules (if touching workflows)
- Code nodes are for data transformation only. All HTTP calls use HTTP Request nodes.
- No monolithic Code nodes
- Never activate crons or post to real Slack channels without Josh's approval
- All test output goes to #test-job-materials

## Key References

- Vercel project: `prj_NCjBLBwLy1jVkKYXsbDEKAHezTVJ`
- Team: `team_PsONISVtN2B0nw6MgdHDsyKL`
- ServiceTitan tenant: `786349683`
- Secrets and tokens: Use environment variables or the Juggernaut MCP server. Never hardcode.

## Install Production Targets
- $8,824/crew/day, $1,000/rev per hour
- Chunking: 1/4=$2,500, 1/2=$5,000, 3/4=$7,500, full=$10,000+
- $0 install-BU jobs are chunking violations
