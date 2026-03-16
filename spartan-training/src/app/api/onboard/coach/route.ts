import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { employee_id, message } = body;
    if (!employee_id || !message) {
      return NextResponse.json({ error: "employee_id and message required" }, { status: 400 });
    }

    const empRows = await query(`SELECT * FROM knowledge_lake.onboarding_employees WHERE id = '${employee_id}'`);
    const emp = empRows?.[0];
    if (!emp) return NextResponse.json({ error: "Employee not found" }, { status: 404 });

    const progress = await query(`
      SELECT t.title, t.category, t.description, p.status
      FROM knowledge_lake.onboarding_progress p
      JOIN knowledge_lake.onboarding_templates t ON t.id = p.template_id
      WHERE p.employee_id = '${employee_id}'
      ORDER BY t.category, t.sort_order
    `);

    const done = progress.filter((p: Record<string, string>) => p.status === "done");
    const pending = progress.filter((p: Record<string, string>) => p.status === "pending");

    const nextItems = pending.slice(0, 5).map((p: Record<string, string>) => `- ${p.title} (${p.category})`).join("\n");

    const recentHistory = await query(`
      SELECT role, content FROM knowledge_lake.onboarding_chat 
      WHERE employee_id = '${employee_id}' ORDER BY created_at DESC LIMIT 10
    `);
    const chatHistory = (recentHistory || []).reverse();

    const systemPrompt = `You are the Spartan Academy Coach — the AI onboarding assistant for Spartan Plumbing LLC in Dayton, Ohio. You're helping ${emp.name} (${emp.role}) get onboarded.

PERSONALITY: You're like a friendly, experienced team lead. Confident but warm. You use casual professional language — not stiff corporate speak. You're encouraging without being cheesy. Think "supportive coworker who knows everything" not "corporate HR bot." Keep responses concise — 2-3 sentences for simple questions, a short paragraph for complex ones. Never write walls of text.

CONTEXT:
- Employee: ${emp.name}, Role: ${emp.role}, Position: ${emp.position || "Not set"}
- Hire date: ${emp.hire_date || "Not set"}
- Progress: ${done.length} of ${progress.length} items completed (${Math.round(100 * done.length / progress.length)}%)
- Next up:\n${nextItems || "Nothing pending — all done!"}

RULES:
- When they ask "what should I do next?" — give them the SPECIFIC next 2-3 pending items by name
- When they ask about a specific process (like Slack setup, ServiceTitan, etc.) — give them concise, actionable steps
- When they complete something, celebrate briefly and point to the next thing
- If they seem stuck or frustrated, empathize and offer to break the task into smaller steps
- Never make up information about Spartan's specific systems — if you don't know, say "I'd check with your manager on that one"
- Reference their role — office staff get different guidance than techs
- Keep it fun and encouraging without being over-the-top`;

    const messages = chatHistory.map((m: Record<string, string>) => ({
      role: m.role,
      content: m.content,
    }));
    messages.push({ role: "user", content: message });

    const openrouterRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${process.env.OPENROUTER_API_KEY || ""}`,
      },
      body: JSON.stringify({
        model: "google/gemini-2.0-flash-001",
        max_tokens: 500,
        messages: [
          { role: "system", content: systemPrompt },
          ...messages,
        ],
      }),
    });

    if (!openrouterRes.ok) {
      const errText = await openrouterRes.text();
      console.error("OpenRouter error:", errText);
      return NextResponse.json({ error: "AI service error" }, { status: 500 });
    }

    const aiData = await openrouterRes.json();
    const reply = aiData.choices?.[0]?.message?.content || "Sorry, I couldn't process that. Try again?";

    const msgEsc = message.replace(/'/g, "''");
    const replyEsc = reply.replace(/'/g, "''");
    await query(`INSERT INTO knowledge_lake.onboarding_chat (employee_id, role, content) VALUES ('${employee_id}', 'user', '${msgEsc}')`);
    await query(`INSERT INTO knowledge_lake.onboarding_chat (employee_id, role, content) VALUES ('${employee_id}', 'assistant', '${replyEsc}')`);

    return NextResponse.json({ reply });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
