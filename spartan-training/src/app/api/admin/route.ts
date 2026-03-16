import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

function esc(s: string) { return (s || "").replace(/'/g, "''"); }

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const adminEmail = searchParams.get("admin_email");
  if (!adminEmail) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const adm = await query(`SELECT id, is_admin FROM knowledge_lake.onboarding_employees WHERE email = '${esc(adminEmail)}' AND is_admin = true`);
    if (!adm?.length) return NextResponse.json({ error: "Not an admin" }, { status: 403 });

    const employees = await query(`
      SELECT e.id, e.name, e.email, e.personal_email, e.phone, e.role, e.position,
             e.hire_date, e.status, e.total_xp, e.level, e.is_admin, e.pin_code,
             e.manager_id, e.due_30_date, e.due_60_date, e.due_90_date,
             e.created_at, e.last_activity_at,
             m.name as manager_name
      FROM knowledge_lake.onboarding_employees e
      LEFT JOIN knowledge_lake.onboarding_employees m ON m.id = e.manager_id
      ORDER BY e.name
    `);

    const progress = await query(`
      SELECT p.employee_id,
             count(*) as total,
             count(*) FILTER (WHERE p.status = 'done') as done,
             sum(t.xp_value) as total_xp,
             sum(t.xp_value) FILTER (WHERE p.status = 'done') as earned_xp
      FROM knowledge_lake.onboarding_progress p
      JOIN knowledge_lake.onboarding_templates t ON t.id = p.template_id
      GROUP BY p.employee_id
    `);

    const progressMap: Record<string, { total: number; done: number; totalXp: number; earnedXp: number }> = {};
    for (const p of progress || []) {
      progressMap[p.employee_id] = {
        total: Number(p.total),
        done: Number(p.done),
        totalXp: Number(p.total_xp),
        earnedXp: Number(p.earned_xp || 0),
      };
    }

    const templates = await query(`
      SELECT role, count(*) as count, sum(xp_value) as total_xp
      FROM knowledge_lake.onboarding_templates
      GROUP BY role ORDER BY role
    `);

    return NextResponse.json({ employees, progressMap, templateStats: templates });
  } catch (e: unknown) {
    return NextResponse.json({ error: e instanceof Error ? e.message : "Error" }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { admin_email, name, email, role, position, hire_date, personal_email, phone, pin_code, is_admin, manager_id } = body;

    const adm = await query(`SELECT id FROM knowledge_lake.onboarding_employees WHERE email = '${esc(admin_email)}' AND is_admin = true`);
    if (!adm?.length) return NextResponse.json({ error: "Not an admin" }, { status: 403 });

    if (!name || !email || !role) return NextResponse.json({ error: "name, email, role required" }, { status: 400 });

    const pin = pin_code || String(100000 + Math.floor(Math.random() * 900000));
    const hd = hire_date ? `'${esc(hire_date)}'` : "CURRENT_DATE";
    const mgr = manager_id ? `'${esc(manager_id)}'` : "NULL";
    const d30 = hire_date ? `'${esc(hire_date)}'::date + 30` : "CURRENT_DATE + 30";
    const d60 = hire_date ? `'${esc(hire_date)}'::date + 60` : "CURRENT_DATE + 60";
    const d90 = hire_date ? `'${esc(hire_date)}'::date + 90` : "CURRENT_DATE + 90";

    const rows = await query(`
      INSERT INTO knowledge_lake.onboarding_employees (name, email, role, position, hire_date, personal_email, phone, pin_code, is_admin, manager_id, due_30_date, due_60_date, due_90_date)
      VALUES ('${esc(name)}', '${esc(email)}', '${esc(role)}', '${esc(position || "")}', ${hd}, '${esc(personal_email || "")}', '${esc(phone || "")}', '${pin}', ${is_admin ? "true" : "false"}, ${mgr}, ${d30}, ${d60}, ${d90})
      ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, role = EXCLUDED.role, position = EXCLUDED.position, is_admin = EXCLUDED.is_admin, manager_id = EXCLUDED.manager_id, updated_at = now()
      RETURNING *
    `);
    const emp = rows[0];

    await query(`
      INSERT INTO knowledge_lake.onboarding_progress (employee_id, template_id)
      SELECT '${emp.id}', t.id
      FROM knowledge_lake.onboarding_templates t
      WHERE t.role IN ('all', '${esc(role)}')
      ON CONFLICT (employee_id, template_id) DO NOTHING
    `);

    return NextResponse.json({ ok: true, employee: emp, generated_pin: pin });
  } catch (e: unknown) {
    return NextResponse.json({ error: e instanceof Error ? e.message : "Error" }, { status: 500 });
  }
}
