"use client";

import { useState, useEffect, useCallback } from "react";

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  password_set_at: string | null;
  invited_by: string | null;
}

export default function UserManagementPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");
  const [showInvite, setShowInvite] = useState(false);
  const [invName, setInvName] = useState("");
  const [invEmail, setInvEmail] = useState("");
  const [invRole, setInvRole] = useState("member");
  const [inviting, setInviting] = useState(false);

  const loadUsers = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/users");
      if (res.status === 403) { window.location.href = "/"; return; }
      const data = await res.json();
      setUsers(data.users || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  function flash(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  }

  async function doAction(action: string, userId: string) {
    const res = await fetch("/api/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, userId }),
    });
    const data = await res.json();
    if (res.ok) {
      flash(data.message);
      loadUsers();
    } else {
      flash(data.error || "Failed");
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!invName || !invEmail) return;
    setInviting(true);
    const res = await fetch("/api/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "invite", name: invName, email: invEmail, role: invRole }),
    });
    const data = await res.json();
    if (res.ok) {
      flash(data.message);
      setInvName(""); setInvEmail(""); setInvRole("member"); setShowInvite(false);
      loadUsers();
    } else {
      flash(data.error || "Failed");
    }
    setInviting(false);
  }

  function fmtDate(d: string | null) {
    if (!d) return "—";
    return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  const active = users.filter(u => u.is_active);
  const inactive = users.filter(u => !u.is_active);

  if (loading) {
    return <div style={{ padding: 40, textAlign: "center", color: "#555" }}>Loading...</div>;
  }

  return (
    <div>
      {toast && (
        <div style={{
          position: "fixed", top: 70, left: "50%", transform: "translateX(-50%)",
          background: "#c8a84e", color: "#0a0a0a", padding: "10px 28px", borderRadius: 20,
          fontWeight: 600, fontSize: 14, zIndex: 400, boxShadow: "0 4px 20px rgba(200,168,78,0.4)",
        }}>
          {toast}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: 4 }}>User Management</h1>
          <p style={{ color: "#555", fontSize: 14 }}>{active.length} active · {inactive.length} deactivated</p>
        </div>
        <button
          className="btn btn-gold"
          onClick={() => setShowInvite(!showInvite)}
        >
          {showInvite ? "Cancel" : "+ Invite User"}
        </button>
      </div>

      {showInvite && (
        <div className="card" style={{ padding: 24, marginBottom: 24 }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 16, color: "#c8a84e" }}>
            Invite New User
          </h3>
          <form onSubmit={handleInvite} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={{ display: "block", fontSize: 12, color: "#999", marginBottom: 4 }}>Full Name</label>
              <input
                value={invName} onChange={e => setInvName(e.target.value)}
                placeholder="John Smith" required
                style={{
                  width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid #222",
                  background: "#0a0a0a", color: "#e8e8e8", fontSize: 14, boxSizing: "border-box",
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: 12, color: "#999", marginBottom: 4 }}>Email</label>
              <input
                type="email" value={invEmail} onChange={e => setInvEmail(e.target.value)}
                placeholder="john@spartan-plumbing.com" required
                style={{
                  width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid #222",
                  background: "#0a0a0a", color: "#e8e8e8", fontSize: 14, boxSizing: "border-box",
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: 12, color: "#999", marginBottom: 4 }}>Role</label>
              <select
                value={invRole} onChange={e => setInvRole(e.target.value)}
                style={{
                  width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid #222",
                  background: "#0a0a0a", color: "#e8e8e8", fontSize: 14, boxSizing: "border-box",
                }}
              >
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div style={{ display: "flex", alignItems: "flex-end" }}>
              <button type="submit" className="btn btn-gold" disabled={inviting}
                style={{ width: "100%" }}>
                {inviting ? "Inviting..." : "Send Invite"}
              </button>
            </div>
          </form>
          <p style={{ fontSize: 12, color: "#555", marginTop: 12 }}>
            They&apos;ll create their own password the first time they visit the site.
          </p>
        </div>
      )}

      <div style={{ display: "grid", gap: 8 }}>
        {active.map(u => (
          <div key={u.id} className="card" style={{
            padding: "16px 20px",
            display: "flex", alignItems: "center", justifyContent: "space-between",
            flexWrap: "wrap", gap: 12,
          }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontWeight: 600, fontSize: 15 }}>{u.name}</span>
                {u.role === "admin" && (
                  <span style={{
                    fontSize: 10, background: "rgba(185,28,28,0.2)", color: "#ef4444",
                    padding: "2px 6px", borderRadius: 4, fontWeight: 600,
                  }}>ADMIN</span>
                )}
                {!u.password_set_at && (
                  <span style={{
                    fontSize: 10, background: "rgba(200,168,78,0.15)", color: "#c8a84e",
                    padding: "2px 6px", borderRadius: 4, fontWeight: 600,
                  }}>PENDING</span>
                )}
              </div>
              <div style={{ fontSize: 13, color: "#555" }}>
                {u.email} · Joined {fmtDate(u.created_at)}
                {u.last_login_at && <> · Last login {fmtDate(u.last_login_at)}</>}
              </div>
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {u.role === "admin" ? (
                <button className="btn btn-outline" style={{ fontSize: 12, padding: "4px 10px" }}
                  onClick={() => doAction("remove_admin", u.id)}>Remove Admin</button>
              ) : (
                <button className="btn btn-outline" style={{ fontSize: 12, padding: "4px 10px" }}
                  onClick={() => doAction("make_admin", u.id)}>Make Admin</button>
              )}
              <button className="btn btn-outline" style={{ fontSize: 12, padding: "4px 10px" }}
                onClick={() => doAction("reset_password", u.id)}>Reset Password</button>
              <button className="btn btn-outline" style={{
                fontSize: 12, padding: "4px 10px",
                borderColor: "rgba(185,28,28,0.4)", color: "#ef4444",
              }}
                onClick={() => {
                  if (confirm(`Deactivate ${u.name}? They won't be able to access the site.`)) {
                    doAction("deactivate", u.id);
                  }
                }}>Deactivate</button>
            </div>
          </div>
        ))}
      </div>

      {inactive.length > 0 && (
        <>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, marginTop: 32, marginBottom: 12, color: "#555" }}>
            Deactivated ({inactive.length})
          </h3>
          <div style={{ display: "grid", gap: 8 }}>
            {inactive.map(u => (
              <div key={u.id} className="card" style={{
                padding: "16px 20px", opacity: 0.5,
                display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <div>
                  <span style={{ fontWeight: 600, fontSize: 15 }}>{u.name}</span>
                  <span style={{ fontSize: 13, color: "#555", marginLeft: 8 }}>{u.email}</span>
                </div>
                <button className="btn btn-outline" style={{ fontSize: 12, padding: "4px 10px" }}
                  onClick={() => doAction("reactivate", u.id)}>Reactivate</button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
