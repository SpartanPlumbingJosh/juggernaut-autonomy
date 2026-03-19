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

    // Look up user
    let rows;
    try {
      rows = await query(
        `SELECT id, email, name, password_hash, role, is_active 
         FROM knowledge_lake.training_users 
         WHERE email = '${email.replace(/'/g, "''").toLowerCase()}'`
      );
    } catch (dbErr) {
      console.error("Login DB error:", dbErr);
      return NextResponse.json({ error: "Database connection failed", detail: String(dbErr) }, { status: 500 });
    }

    if (!rows || rows.length === 0) {
      return NextResponse.json({ error: "No account found. Ask your admin for an invite." }, { status: 401 });
    }

    const user = rows[0];

    // Check if account is deactivated
    if (!user.is_active) {
      return NextResponse.json({ error: "Your account has been deactivated. Contact your admin." }, { status: 403 });
    }

    // Check if they haven't set a password yet
    if (!user.password_hash) {
      return NextResponse.json({
        error: "You need to create a password first.",
        needsPassword: true,
      }, { status: 401 });
    }

    // Verify password
    let valid;
    try {
      valid = await bcrypt.compare(password, user.password_hash);
    } catch (bcryptErr) {
      console.error("Login bcrypt error:", bcryptErr);
      return NextResponse.json({ error: "Password verification failed", detail: String(bcryptErr) }, { status: 500 });
    }

    if (!valid) {
      return NextResponse.json({ error: "Invalid password." }, { status: 401 });
    }

    // Update last_login_at (non-blocking, don't let it crash login)
    query(
      `UPDATE knowledge_lake.training_users SET last_login_at = now() WHERE id = '${user.id}'`
    ).catch(() => {});

    // Create JWT and set cookie
    let token;
    try {
      token = await createToken({
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
      });
    } catch (jwtErr) {
      console.error("Login JWT error:", jwtErr);
      return NextResponse.json({ error: "Token creation failed", detail: String(jwtErr) }, { status: 500 });
    }

    try {
      await setSessionCookie(token);
    } catch (cookieErr) {
      console.error("Login cookie error:", cookieErr);
      return NextResponse.json({ error: "Cookie set failed", detail: String(cookieErr) }, { status: 500 });
    }

    return NextResponse.json({
      ok: true,
      user: { id: user.id, email: user.email, name: user.name, role: user.role },
    });
  } catch (err) {
    console.error("Login error:", err);
    return NextResponse.json({ error: "Internal error", detail: String(err) }, { status: 500 });
  }
}
