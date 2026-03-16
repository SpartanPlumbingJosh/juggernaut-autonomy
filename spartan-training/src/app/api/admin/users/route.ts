import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { query } from "@/lib/supabase";

// GET - list all users
export async function GET() {
  const session = await getSession();
  if (!session || session.role !== "admin") {
    return NextResponse.json({ error: "Admin only" }, { status: 403 });
  }

  const rows = await query(
    `SELECT id, email, name, role, is_active, created_at, last_login_at, password_set_at, invited_by
     FROM knowledge_lake.training_users
     ORDER BY created_at DESC`
  );

  return NextResponse.json({ users: rows || [] });
}

// POST - invite new user, deactivate, reactivate, reset password
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session || session.role !== "admin") {
    return NextResponse.json({ error: "Admin only" }, { status: 403 });
  }

  const body = await req.json();
  const { action } = body;

  if (action === "invite") {
    const { email, name, role } = body;
    if (!email || !name) {
      return NextResponse.json({ error: "Email and name required" }, { status: 400 });
    }

    // Check if user already exists
    const existing = await query(
      `SELECT id FROM knowledge_lake.training_users WHERE email = '${email.replace(/'/g, "''").toLowerCase()}'`
    );
    if (existing && existing.length > 0) {
      return NextResponse.json({ error: "User with this email already exists" }, { status: 409 });
    }

    await query(
      `INSERT INTO knowledge_lake.training_users (email, name, role, invited_by)
       VALUES ('${email.replace(/'/g, "''").toLowerCase()}', '${name.replace(/'/g, "''")}', '${role || "member"}', '${session.email}')`
    );

    return NextResponse.json({ ok: true, message: `${name} invited. They can set their password at the login page.` });
  }

  if (action === "deactivate") {
    const { userId } = body;
    if (!userId) return NextResponse.json({ error: "userId required" }, { status: 400 });

    // Don't let admin deactivate themselves
    if (userId === session.id) {
      return NextResponse.json({ error: "You can't deactivate yourself" }, { status: 400 });
    }

    await query(
      `UPDATE knowledge_lake.training_users SET is_active = false WHERE id = '${userId}'`
    );
    return NextResponse.json({ ok: true, message: "User deactivated. They'll be blocked on next request." });
  }

  if (action === "reactivate") {
    const { userId } = body;
    if (!userId) return NextResponse.json({ error: "userId required" }, { status: 400 });

    await query(
      `UPDATE knowledge_lake.training_users SET is_active = true WHERE id = '${userId}'`
    );
    return NextResponse.json({ ok: true, message: "User reactivated." });
  }

  if (action === "reset_password") {
    const { userId } = body;
    if (!userId) return NextResponse.json({ error: "userId required" }, { status: 400 });

    await query(
      `UPDATE knowledge_lake.training_users SET password_hash = NULL, password_set_at = NULL WHERE id = '${userId}'`
    );
    return NextResponse.json({ ok: true, message: "Password reset. User will need to set a new one at login." });
  }

  if (action === "make_admin") {
    const { userId } = body;
    if (!userId) return NextResponse.json({ error: "userId required" }, { status: 400 });

    await query(
      `UPDATE knowledge_lake.training_users SET role = 'admin' WHERE id = '${userId}'`
    );
    return NextResponse.json({ ok: true, message: "User promoted to admin." });
  }

  if (action === "remove_admin") {
    const { userId } = body;
    if (!userId) return NextResponse.json({ error: "userId required" }, { status: 400 });

    if (userId === session.id) {
      return NextResponse.json({ error: "You can't remove your own admin access" }, { status: 400 });
    }

    await query(
      `UPDATE knowledge_lake.training_users SET role = 'member' WHERE id = '${userId}'`
    );
    return NextResponse.json({ ok: true, message: "Admin access removed." });
  }

  return NextResponse.json({ error: "Unknown action" }, { status: 400 });
}
