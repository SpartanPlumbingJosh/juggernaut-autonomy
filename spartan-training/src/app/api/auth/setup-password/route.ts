import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { query } from "@/lib/supabase";
import { createToken, setSessionCookie } from "@/lib/auth";

export async function POST(req: NextRequest) {
  try {
    const { email, password } = await req.json();

    if (!email || !password) {
      return NextResponse.json({ error: "Email and password required" }, { status: 400 });
    }

    if (password.length < 8) {
      return NextResponse.json({ error: "Password must be at least 8 characters" }, { status: 400 });
    }

    // Look up user
    const rows = await query(
      `SELECT id, email, name, password_hash, role, is_active 
       FROM knowledge_lake.training_users 
       WHERE email = '${email.replace(/'/g, "''").toLowerCase()}'`
    );

    if (!rows || rows.length === 0) {
      return NextResponse.json({ error: "No account found. Ask your admin for an invite." }, { status: 401 });
    }

    const user = rows[0];

    if (!user.is_active) {
      return NextResponse.json({ error: "Your account has been deactivated." }, { status: 403 });
    }

    // Only allow password setup if they don't have one yet
    if (user.password_hash) {
      return NextResponse.json({ error: "Password already set. Use the login page." }, { status: 400 });
    }

    // Hash and save password
    const hash = await bcrypt.hash(password, 12);
    await query(
      `UPDATE knowledge_lake.training_users 
       SET password_hash = '${hash.replace(/'/g, "''")}', 
           password_set_at = now(), 
           last_login_at = now() 
       WHERE id = '${user.id}'`
    );

    // Create JWT and set cookie — log them in immediately
    const token = await createToken({
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
    });

    await setSessionCookie(token);

    return NextResponse.json({
      ok: true,
      user: { id: user.id, email: user.email, name: user.name, role: user.role },
    });
  } catch (err) {
    console.error("Setup password error:", err);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
