import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { employee_id, template_id, status, value, completed_by } = body;
    if (!employee_id || !template_id) {
      return NextResponse.json({ error: "employee_id and template_id required" }, { status: 400 });
    }

    const s = status || "done";
    const v = (value || "").replace(/'/g, "''");
    const cb = (completed_by || "self").replace(/'/g, "''");

    await query(`
      UPDATE knowledge_lake.onboarding_progress 
      SET status = '${s}', value = '${v}', completed_by = '${cb}', 
          completed_at = ${s === "done" ? "now()" : "NULL"}
      WHERE employee_id = '${employee_id}' AND template_id = '${template_id}'
    `);

    const xpRows = await query(`
      SELECT COALESCE(sum(t.xp_value), 0) as total
      FROM knowledge_lake.onboarding_progress p
      JOIN knowledge_lake.onboarding_templates t ON t.id = p.template_id
      WHERE p.employee_id = '${employee_id}' AND p.status = 'done'
    `);
    const newXp = Number(xpRows?.[0]?.total || 0);

    await query(`
      UPDATE knowledge_lake.onboarding_employees 
      SET total_xp = ${newXp}, last_activity_at = now(), updated_at = now()
      WHERE id = '${employee_id}'
    `);

    const doneCount = await query(`
      SELECT count(*) as cnt FROM knowledge_lake.onboarding_progress 
      WHERE employee_id = '${employee_id}' AND status = 'done'
    `);
    const done = Number(doneCount?.[0]?.cnt || 0);

    const badges: Array<{ code: string; name: string; desc: string }> = [];
    if (done === 1) badges.push({ code: "first_step", name: "First Step", desc: "Completed your first task" });
    if (done >= 5) badges.push({ code: "on_a_roll", name: "On a Roll", desc: "Completed 5 tasks" });
    if (done >= 15) badges.push({ code: "halfway_hero", name: "Halfway Hero", desc: "Completed 15 tasks" });
    if (done >= 30) badges.push({ code: "unstoppable", name: "Unstoppable", desc: "Completed 30 tasks" });

    const catCheck = await query(`
      SELECT t.category, count(*) as total,
        count(*) FILTER (WHERE p.status = 'done') as completed
      FROM knowledge_lake.onboarding_progress p
      JOIN knowledge_lake.onboarding_templates t ON t.id = p.template_id
      WHERE p.employee_id = '${employee_id}'
      GROUP BY t.category
      HAVING count(*) = count(*) FILTER (WHERE p.status = 'done')
    `);
    for (const c of catCheck || []) {
      badges.push({ code: `cat_${c.category.toLowerCase().replace(/\s+/g, "_")}`, name: `${c.category} Complete`, desc: `Finished all ${c.category} tasks` });
    }

    const newBadges: typeof badges = [];
    for (const b of badges) {
      try {
        await query(`
          INSERT INTO knowledge_lake.onboarding_achievements (employee_id, badge_code, badge_name, badge_description)
          VALUES ('${employee_id}', '${b.code}', '${b.name}', '${b.desc}')
          ON CONFLICT (employee_id, badge_code) DO NOTHING
        `);
        const check = await query(`SELECT earned_at FROM knowledge_lake.onboarding_achievements WHERE employee_id = '${employee_id}' AND badge_code = '${b.code}'`);
        if (check?.[0]) newBadges.push(b);
      } catch { /* badge already exists */ }
    }

    return NextResponse.json({ ok: true, xp: newXp, completedCount: done, newBadges });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
