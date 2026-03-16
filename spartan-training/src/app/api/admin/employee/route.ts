import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

function esc(s: string) { return (s || "").replace(/'/g, "''"); }

export async function PUT(req: Request) {
  try {
    const body = await req.json();
    const { admin_email, employee_id, ...fields } = body;

    const adm = await query(`SELECT id FROM knowledge_lake.onboarding_employees WHERE email = '${esc(admin_email)}' AND is_admin = true`);
    if (!adm?.length) return NextResponse.json({ error: "Not an admin" }, { status: 403 });

    const sets: string[] = [];
    if (fields.name !== undefined) sets.push(`name = '${esc(fields.name)}'`);
    if (fields.role !== undefined) sets.push(`role = '${esc(fields.role)}'`);
    if (fields.position !== undefined) sets.push(`position = '${esc(fields.position)}'`);
    if (fields.status !== undefined) sets.push(`status = '${esc(fields.status)}'`);
    if (fields.is_admin !== undefined) sets.push(`is_admin = ${fields.is_admin ? "true" : "false"}`);
    if (fields.pin_code !== undefined) sets.push(`pin_code = '${esc(fields.pin_code)}'`);
    if (fields.phone !== undefined) sets.push(`phone = '${esc(fields.phone)}'`);
    if (fields.personal_email !== undefined) sets.push(`personal_email = '${esc(fields.personal_email)}'`);
    if (fields.manager_id !== undefined) sets.push(`manager_id = ${fields.manager_id ? `'${esc(fields.manager_id)}'` : "NULL"}`);
    sets.push("updated_at = now()");

    const rows = await query(`UPDATE knowledge_lake.onboarding_employees SET ${sets.join(", ")} WHERE id = '${esc(employee_id)}' RETURNING *`);
    return NextResponse.json({ ok: true, employee: rows?.[0] });
  } catch (e: unknown) {
    return NextResponse.json({ error: e instanceof Error ? e.message : "Error" }, { status: 500 });
  }
}

export async function DELETE(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const adminEmail = searchParams.get("admin_email");
    const employeeId = searchParams.get("id");

    const adm = await query(`SELECT id FROM knowledge_lake.onboarding_employees WHERE email = '${esc(adminEmail || "")}' AND is_admin = true`);
    if (!adm?.length) return NextResponse.json({ error: "Not an admin" }, { status: 403 });

    await query(`UPDATE knowledge_lake.onboarding_employees SET status = 'inactive', updated_at = now() WHERE id = '${esc(employeeId || "")}'`);
    return NextResponse.json({ ok: true });
  } catch (e: unknown) {
    return NextResponse.json({ error: e instanceof Error ? e.message : "Error" }, { status: 500 });
  }
}
