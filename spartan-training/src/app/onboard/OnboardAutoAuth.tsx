"use client";
import { useEffect, useState } from "react";
import { OnboardingApp } from "./OnboardingApp";

export function OnboardAutoAuth() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Fetch current JWT user and pre-populate sessionStorage
    // so OnboardingApp skips its internal PIN login
    async function init() {
      try {
        const res = await fetch("/api/auth/me");
        if (res.ok) {
          const data = await res.json();
          if (data.email) {
            sessionStorage.setItem("sa_email", data.email);
          }
        }
      } catch { /* proceed anyway */ }
      setReady(true);
    }
    init();
  }, []);

  if (!ready) {
    return (
      <div style={{ padding: 60, textAlign: "center", color: "var(--text3)" }}>
        Loading onboarding...
      </div>
    );
  }

  return <OnboardingApp />;
}
