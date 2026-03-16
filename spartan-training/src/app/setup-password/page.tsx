"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

function SetupPasswordForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const e = params.get("email");
    if (e) setEmail(e);
  }, [params]);

  async function handleSetup(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/setup-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.toLowerCase().trim(), password }),
      });
      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Failed to set password");
        setLoading(false);
        return;
      }

      router.push("/");
      router.refresh();
    } catch {
      setError("Network error. Try again.");
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0a0a0a",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
    }}>
      <div style={{
        width: "100%",
        maxWidth: 400,
        background: "#111",
        border: "1px solid #222",
        borderRadius: 16,
        padding: 40,
      }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="https://spartan-plumbing.com/wp-content/uploads/spartan-logo-nav.svg"
            alt="Spartan Plumbing"
            style={{ height: 48, margin: "0 auto 16px" }}
          />
          <h1 style={{
            fontSize: "1.3rem",
            fontWeight: 700,
            fontFamily: "'Archivo Black', sans-serif",
            color: "#c8a84e",
            marginBottom: 4,
          }}>
            CREATE YOUR PASSWORD
          </h1>
          <p style={{ color: "#555", fontSize: 14 }}>
            You&apos;ve been invited to Spartan Academy
          </p>
        </div>

        <form onSubmit={handleSetup}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontSize: 12, color: "#999", marginBottom: 6, fontWeight: 500 }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@spartan-plumbing.com"
              required
              style={{
                width: "100%", padding: "12px 14px", borderRadius: 8,
                border: "1px solid #222", background: "#0a0a0a", color: "#e8e8e8",
                fontSize: 14, outline: "none", boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontSize: 12, color: "#999", marginBottom: 6, fontWeight: 500 }}>
              New Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              required
              autoComplete="new-password"
              style={{
                width: "100%", padding: "12px 14px", borderRadius: 8,
                border: "1px solid #222", background: "#0a0a0a", color: "#e8e8e8",
                fontSize: 14, outline: "none", boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label style={{ display: "block", fontSize: 12, color: "#999", marginBottom: 6, fontWeight: 500 }}>
              Confirm Password
            </label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Type it again"
              required
              autoComplete="new-password"
              style={{
                width: "100%", padding: "12px 14px", borderRadius: 8,
                border: "1px solid #222", background: "#0a0a0a", color: "#e8e8e8",
                fontSize: 14, outline: "none", boxSizing: "border-box",
              }}
            />
          </div>

          {error && (
            <div style={{
              padding: "10px 14px", borderRadius: 8,
              background: "rgba(185,28,28,0.1)", border: "1px solid rgba(185,28,28,0.3)",
              color: "#ef4444", fontSize: 13, marginBottom: 16,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%", padding: "12px 20px", borderRadius: 8, border: "none",
              background: loading ? "#666" : "#c8a84e", color: "#0a0a0a",
              fontSize: 15, fontWeight: 700, cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Setting up..." : "Create Password & Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function SetupPasswordPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh", background: "#0a0a0a" }} />}>
      <SetupPasswordForm />
    </Suspense>
  );
}
