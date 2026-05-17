"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Activity, LogIn } from "lucide-react";
import { api, setToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

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
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-sm">
      <CardHeader className="items-center text-center">
        <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Activity className="h-5 w-5" />
        </div>
        <CardTitle className="text-lg">Lulan Analyzer Pro</CardTitle>
        <CardDescription>
          Research-only DICOM analysis workstation
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-xs">
            <span className="text-muted-foreground">Email</span>
            <input
              type="email"
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="block text-xs">
            <span className="text-muted-foreground">Password</span>
            <input
              type="password"
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && (
            <div className="rounded-md bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
              {error}
            </div>
          )}
          <Button type="submit" disabled={loading} className="w-full">
            <LogIn className="h-4 w-4" />
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-[10px] text-muted-foreground">
          Demo accounts are seeded by{" "}
          <code className="rounded bg-muted px-1 font-mono">make seed</code>.
        </p>
      </CardContent>
    </Card>
  );
}
