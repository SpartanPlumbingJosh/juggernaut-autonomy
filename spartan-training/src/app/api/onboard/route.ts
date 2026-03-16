import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const email = searchParams.get("email");
  if (!email) return NextResponse.json({ error: "email required" }, { status: 400 });

  try {
    const e = email.replace(/'/g, "''");
    const employees = await query(`SELECT * FROM knowledge_lake.onboarding_employees WHERE email = '${e}'`);
    if (!employees || employees.length === 0) return NextResponse.json(null);

    const emp = employees[0];
    const role = emp.role;

    const templates = await query(`
      SELECT t.*, p.status as progress_status, p.value as progress_value, 
             p.completed_at, p.completed_by, p.notes
      FROM knowledge_lake.onboarding_templates t
      LEFT JOIN knowledge_lake.onboarding_progress p 
        ON p.template_id = t.id AND p.employee_id = '${emp.id}'
      WHERE t.role IN ('all', '${role}')
      ORDER BY t.category, t.sort_order
    `);

    const achievements = await query(
      `SELECT * FROM knowledge_lake.onboarding_achievements WHERE employee_id = '${emp.id}' ORDER BY earned_at`
    );

    const categories: Record<string, { items: typeof templates; done: number; total: number }> = {};
    let totalXp = 0;
    let earnedXp = 0;

    for (const t of templates) {
      if (!categories[t.category]) categories[t.category] = { items: [], done: 0, total: 0 };
      categories[t.category].items.push(t);
      categories[t.category].total++;
      totalXp += Number(t.xp_value);
      if (t.progress_status === "done") {
        categories[t.category].done++;
        earnedXp += Number(t.xp_value);
      }
    }

    let level = 1;
    let levelName = "Recruit";
    if (earnedXp >= 700) { level = 5; levelName = "Spartan"; }
    else if (earnedXp >= 450) { level = 4; levelName = "Journeyman"; }
    else if (earnedXp >= 250) { level = 3; levelName = "Apprentice"; }
    else if (earnedXp >= 100) { level = 2; levelName = "Trainee"; }

    return NextResponse.json({
      employee: emp,
      categories,
      achievements: achievements || [],
      stats: { totalXp, earnedXp, level, levelName, totalItems: templates.length, completedItems: templates.filter((t: Record<string, unknown>) => t.progress_status === "done").length },
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { name, email, role, position, hire_date, personal_email, phone } = body;
    if (!name || !email || !role) {
      return NextResponse.json({ error: "name, email, and role required" }, { status: 400 });
    }

    const n = name.replace(/'/g, "''");
    const em = email.replace(/'/g, "''");
    const pos = (position || "").replace(/'/g, "''");
    const pe = (personal_email || "").replace(/'/g, "''");
    const ph = (phone || "").replace(/'/g, "''");
    const hd = hire_date || "now()";

    const rows = await query(`
      INSERT INTO knowledge_lake.onboarding_employees (name, email, role, position, hire_date, personal_email, phone)
      VALUES ('${n}', '${em}', '${role}', '${pos}', '${hd === "now()" ? "now()" : "'" + hd + "'"}', '${pe}', '${ph}')
      ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, role = EXCLUDED.role, updated_at = now()
      RETURNING *
    `);
    const emp = rows[0];

    await query(`
      INSERT INTO knowledge_lake.onboarding_progress (employee_id, template_id)
      SELECT '${emp.id}', t.id
      FROM knowledge_lake.onboarding_templates t
      WHERE t.role IN ('all', '${role}')
      ON CONFLICT (employee_id, template_id) DO NOTHING
    `);

    return NextResponse.json(emp);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
