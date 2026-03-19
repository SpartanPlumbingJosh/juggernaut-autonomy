"use client";

import { useState, useEffect } from "react";
import { OnboardingApp } from "./OnboardingApp";

// Same overlay pattern as admin — renders OnboardingApp immediately
// so its useEffect fires, but covers it until API data is loaded.
export default function OnboardPage() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        const res = await fetch("/api/auth/me");
        if (res.ok) {
          const me = await res.json();
          const email = me.user?.email;
          if (email) {
            sessionStorage.setItem("sa_email", email);
            // Pre-warm the onboard API
            await fetch(`/api/onboard?email=${encodeURIComponent(email)}`);
          }
        }
      } catch { /* proceed */ }
      await new Promise(r => setTimeout(r, 300));
      setReady(true);
    }
    init();
  }, []);

  return (
    <div style={{ position: "relative", minHeight: "60vh" }}>
      {!ready && (
        <div style={{
          position: "fixed", inset: 0, background: "#0a0a0a", zIndex: 150,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <div style={{ color: "#555", fontSize: 14, fontFamily: "'Barlow Condensed', sans-serif" }}>
            Loading...
          </div>
        </div>
      )}
      <OnboardingApp />
    </div>
  );
}
