"use client";

import { useRouter } from "next/navigation";
import { LogOut, User as UserIcon } from "lucide-react";
import useSWR from "swr";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { request, setToken } from "@/lib/api";

type Me = {
  user_id: string;
  email: string;
  role: string;
  full_name: string;
};

export function UserMenu() {
  const router = useRouter();
  const { data } = useSWR<Me>("/auth/me", (k: string) => request<Me>(k), {
    shouldRetryOnError: false,
  });
  if (!data) {
    return (
      <button
        onClick={() => router.push("/login")}
        className="text-xs text-muted-foreground hover:text-foreground"
      >
        Sign in
      </button>
    );
  }
  const initials = data.full_name
    ? data.full_name
        .split(" ")
        .map((p) => p[0])
        .slice(0, 2)
        .join("")
    : data.email.slice(0, 2);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="rounded-full ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
        <Avatar initials={initials} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          <div className="flex flex-col gap-1 normal-case tracking-normal">
            <span className="text-xs font-semibold text-foreground">
              {data.full_name || data.email}
            </span>
            <span className="text-[10px] text-muted-foreground">
              {data.email}
            </span>
            <Badge
              variant={data.role === "admin" ? "warning" : "secondary"}
              className="self-start"
            >
              {data.role}
            </Badge>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => router.push("/admin/audit")}>
          <UserIcon /> Audit log
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => {
            setToken(null);
            router.push("/login");
          }}
        >
          <LogOut /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
