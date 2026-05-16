"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("clinician@lulan.local");
  const [password, setPassword] = useState("clinician_demo_password");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const r = await api.login(email, password);
      setToken(r.token);
      router.push("/worklist");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto mt-12 bg-white border rounded p-6 shadow-sm">
      <h1 className="text-lg font-semibold mb-4">Sign in</h1>
      <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm">
          <span className="text-gray-700">Email</span>
          <input
            type="email"
            className="mt-1 w-full border rounded px-2 py-1.5 text-sm"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label className="block text-sm">
          <span className="text-gray-700">Password</span>
          <input
            type="password"
            className="mt-1 w-full border rounded px-2 py-1.5 text-sm"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <div className="text-sm text-red-600">{error}</div>}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gray-900 text-white rounded py-1.5 text-sm hover:bg-gray-800 disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="mt-3 text-xs text-gray-500">
        Demo accounts are seeded by{" "}
        <code className="bg-gray-100 px-1 rounded">make seed</code>.
      </p>
    </div>
  );
}
