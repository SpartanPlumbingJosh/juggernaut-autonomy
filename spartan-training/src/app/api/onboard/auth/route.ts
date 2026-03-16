import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { email, pin } = body;
    if (!email || !pin) {
      return NextResponse.json({ error: "Email and PIN required" }, { status: 400 });
    }
    const e = email.replace(/'/g, "''");
    const p = pin.replace(/'/g, "''");
    const rows = await query(
      `SELECT id, name, email, role, position, hire_date, total_xp, level, pin_code FROM knowledge_lake.onboarding_employees WHERE email = '${e}'`
    );
    if (!rows || rows.length === 0) {
      return NextResponse.json({ error: "Account not found" }, { status: 404 });
    }
    const emp = rows[0];
    if (!emp.pin_code || emp.pin_code !== p) {
      return NextResponse.json({ error: "Invalid PIN" }, { status: 401 });
    }
    const { pin_code, ...safe } = emp;
    return NextResponse.json(safe);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
