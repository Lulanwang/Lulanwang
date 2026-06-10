"use client";

import { useRef, useState } from "react";
import { Send, ShieldAlert, Sparkles, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

type Msg = { role: "user" | "assistant"; content: string };

const SUGGESTED = [
  "What's the differential?",
  "Rewrite this for the referring clinician.",
  "List teaching points.",
  "Compare to typical findings.",
];

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("lulan_token");
}

export function MedGemmaChat({ studyId }: { studyId: string }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setError(null);
    const next: Msg[] = [
      ...messages,
      { role: "user", content: trimmed },
      { role: "assistant", content: "" },
    ];
    setMessages(next);
    setInput("");
    setBusy(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const tok = getToken();
      const resp = await fetch(`/api/v1/studies/${studyId}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
        },
        body: JSON.stringify({
          messages: next.slice(0, -1), // exclude the empty assistant placeholder
        }),
        signal: ctrl.signal,
      });
      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);
          try {
            const obj = JSON.parse(payload);
            if (obj.error) {
              setError(obj.error);
              continue;
            }
            if (obj.delta) {
              setMessages((cur) => {
                const copy = [...cur];
                const last = copy[copy.length - 1];
                if (last && last.role === "assistant") {
                  copy[copy.length - 1] = {
                    ...last,
                    content: last.content + obj.delta,
                  };
                }
                return copy;
              });
            }
          } catch {
            // ignore malformed chunk
          }
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  return (
    <div className="flex h-full min-h-[400px] flex-col">
      <div className="border-b bg-warning/10 px-3 py-1.5 text-[10px] text-warning">
        <span className="inline-flex items-center gap-1">
          <ShieldAlert className="h-3 w-3" /> RESEARCH ONLY — MedGemma
          responses are unverified and must not influence patient care.
        </span>
      </div>

      <ScrollArea className="flex-1 px-3 py-3">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 py-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
              <Sparkles className="h-5 w-5 text-primary" />
            </div>
            <p className="text-center text-xs text-muted-foreground">
              Ask MedGemma about this study. It sees your accepted findings
              + study metadata, not the pixel data.
            </p>
            <div className="flex flex-wrap justify-center gap-1">
              {SUGGESTED.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-border bg-card px-2 py-0.5 text-[10px] text-foreground hover:border-primary/40 hover:bg-muted"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {messages.map((m, i) => (
              <Bubble key={i} msg={m} pending={busy && i === messages.length - 1} />
            ))}
            {error && (
              <Card className="border-destructive/30">
                <CardContent className="pt-3 text-xs text-destructive">
                  {error}
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </ScrollArea>

      <form
        className="flex items-center gap-2 border-t p-2"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask MedGemma…"
          className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          disabled={busy}
        />
        {messages.length > 0 && (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => {
              setMessages([]);
              setError(null);
            }}
            disabled={busy}
            title="Clear chat"
          >
            <Trash2 />
          </Button>
        )}
        <Button type="submit" size="sm" disabled={busy || !input.trim()}>
          <Send />
          Send
        </Button>
      </form>
    </div>
  );
}

function Bubble({ msg, pending }: { msg: Msg; pending: boolean }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex flex-col gap-1", isUser ? "items-end" : "items-start")}>
      <Badge variant={isUser ? "secondary" : "ai"}>
        {isUser ? "You" : "MedGemma"}
      </Badge>
      <div
        className={cn(
          "max-w-[90%] whitespace-pre-wrap rounded-lg px-3 py-2 text-xs leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground"
        )}
      >
        {msg.content || (pending ? <Skeleton className="h-3 w-32" /> : "")}
      </div>
    </div>
  );
}
