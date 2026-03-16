import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

function esc(s: string) { return (s || "").replace(/'/g, "''"); }

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const adminEmail = searchParams.get("admin_email");
  const role = searchParams.get("role");

  const adm = await query(`SELECT id FROM knowledge_lake.onboarding_employees WHERE email = '${esc(adminEmail || "")}' AND is_admin = true`);
  if (!adm?.length) return NextResponse.json({ error: "Not an admin" }, { status: 403 });

  const where = role ? `WHERE role = '${esc(role)}'` : "";
  const templates = await query(`SELECT * FROM knowledge_lake.onboarding_templates ${where} ORDER BY role, category, sort_order`);
  return NextResponse.json({ templates });
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { admin_email, role, category, title, description, xp_value, requires_value, value_label, requires_manager_approval, sort_order } = body;

    const adm = await query(`SELECT id FROM knowledge_lake.onboarding_employees WHERE email = '${esc(admin_email)}' AND is_admin = true`);
    if (!adm?.length) return NextResponse.json({ error: "Not an admin" }, { status: 403 });

    const so = sort_order || 99;
    const rows = await query(`
      INSERT INTO knowledge_lake.onboarding_templates (role, category, title, description, xp_value, requires_value, value_label, requires_manager_approval, sort_order)
      VALUES ('${esc(role)}', '${esc(category)}', '${esc(title)}', '${esc(description || "")}', ${xp_value || 10}, ${requires_value ? "true" : "false"}, '${esc(value_label || "")}', ${requires_manager_approval ? "true" : "false"}, ${so})
      RETURNING *
    `);
    return NextResponse.json({ ok: true, template: rows?.[0] });
  } catch (e: unknown) {
    return NextResponse.json({ error: e instanceof Error ? e.message : "Error" }, { status: 500 });
  }
}

export async function PUT(req: Request) {
  try {
    const body = await req.json();
    const { admin_email, id, ...fields } = body;

    const adm = await query(`SELECT id FROM knowledge_lake.onboarding_employees WHERE email = '${esc(admin_email)}' AND is_admin = true`);
    if (!adm?.length) return NextResponse.json({ error: "Not an admin" }, { status: 403 });

    const sets: string[] = [];
    if (fields.title !== undefined) sets.push(`title = '${esc(fields.title)}'`);
    if (fields.description !== undefined) sets.push(`description = '${esc(fields.description)}'`);
    if (fields.category !== undefined) sets.push(`category = '${esc(fields.category)}'`);
    if (fields.xp_value !== undefined) sets.push(`xp_value = ${fields.xp_value}`);
    if (fields.sort_order !== undefined) sets.push(`sort_order = ${fields.sort_order}`);
    if (fields.requires_manager_approval !== undefined) sets.push(`requires_manager_approval = ${fields.requires_manager_approval}`);
    if (fields.requires_value !== undefined) sets.push(`requires_value = ${fields.requires_value}`);

    if (!sets.length) return NextResponse.json({ error: "Nothing to update" }, { status: 400 });

    const rows = await query(`UPDATE knowledge_lake.onboarding_templates SET ${sets.join(", ")} WHERE id = '${esc(id)}' RETURNING *`);
    return NextResponse.json({ ok: true, template: rows?.[0] });
  } catch (e: unknown) {
    return NextResponse.json({ error: e instanceof Error ? e.message : "Error" }, { status: 500 });
  }
}
