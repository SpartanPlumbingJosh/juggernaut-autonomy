"use client";

import { useState, useEffect } from "react";
import { OnboardingApp } from "./OnboardingApp";

// Pre-seed sessionStorage and warm the onboard API before OnboardingApp mounts
// so it skips its internal PIN login screen.
export default function OnboardPage() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        const meRes = await fetch("/api/auth/me");
        if (!meRes.ok) { setReady(true); return; }
        const me = await meRes.json();
        const email = me.user?.email;
        if (!email) { setReady(true); return; }

        // Seed sessionStorage BEFORE OnboardingApp mounts
        sessionStorage.setItem("sa_email", email);

        // Pre-warm the onboard API
        await fetch(`/api/onboard?email=${encodeURIComponent(email)}`);
      } catch { /* proceed anyway */ }
      setReady(true);
    }
    init();
  }, []);

  if (!ready) {
    return (
      <div style={{ padding: 60, textAlign: "center", color: "#555", fontSize: 14 }}>
        Loading onboarding...
      </div>
    );
  }

  return <OnboardingApp />;
}
