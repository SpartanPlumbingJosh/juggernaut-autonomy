# Langfuse Tracing Setup

## What It Does

Langfuse traces every LLM call across all JUGGERNAUT workers — prompts, completions, token usage, latency, cost, and errors. Gives you a dashboard to see exactly what the system is doing and where money is going.

## Quick Start (Langfuse Cloud — Free Tier)

1. Sign up at [cloud.langfuse.com](https://cloud.langfuse.com)
2. Create a project called "JUGGERNAUT"
3. Copy your Public Key and Secret Key
4. Set env vars on the Railway engine service:

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

That's it. Tracing starts automatically on next deploy.

## What Gets Traced

| Call Path | Trace Name | What's Captured |
|---|---|---|
| `AIExecutor.chat()` | `ai_executor.chat` | Prompt, completion, model, tokens, latency |
| `AIExecutor.chat_with_tools()` | `ai_executor.chat_with_tools` | Full agentic loop — iterations, tool calls, final output |

Each trace includes:
- **Input**: Last message in the conversation (truncated to 2000 chars)
- **Output**: Model response (truncated to 2000 chars)
- **Model**: Actual model used (from response, not just requested)
- **Usage**: Prompt tokens, completion tokens, total tokens
- **Metadata**: Worker ID, task ID, iteration count, tool call count
- **Errors**: HTTP errors, timeouts, invalid responses

## Graceful Degradation

If `LANGFUSE_PUBLIC_KEY` is not set or the `langfuse` package isn't installed, all tracing calls are no-ops with zero overhead. The engine runs exactly the same.

## Verifying

After deploy, go to your Langfuse dashboard → Traces. You should see traces appearing within 60 seconds of the engine making LLM calls.

## Self-Hosted (Optional)

If you outgrow the free tier:

```bash
docker run -d \
  -e DATABASE_URL=postgresql://... \
  -e NEXTAUTH_SECRET=your-secret \
  -e NEXTAUTH_URL=https://langfuse.yourdomain.com \
  -p 3000:3000 \
  langfuse/langfuse
```

Then set `LANGFUSE_HOST=https://langfuse.yourdomain.com` on the engine.

## Disabling

Remove `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` from Railway env vars. Tracing stops immediately, no code changes needed.
