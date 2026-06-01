"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import clsx from "clsx";
import {
  LayoutDashboard,
  FileText,
  ClipboardList,
  Bot,
  Users,
  UserCircle,
  LogOut,
  Shield,
  ChevronRight,
  Calculator,
  CalendarDays,
  BookOpen,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

type NavItem = {
  label: string;
  href: string;
  icon: React.ReactNode;
  adminOnly?: boolean;
  superadminOnly?: boolean;
};

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: <LayoutDashboard size={18} /> },
  { label: "Facturas DIAN", href: "/facturas", icon: <FileText size={18} /> },
  { label: "Exógenas", href: "/exogenas", icon: <ClipboardList size={18} /> },
  { label: "Nómina", href: "/nomina", icon: <Calculator size={18} /> },
  { label: "Renta", href: "/renta", icon: <BookOpen size={18} /> },
  { label: "Calendario DIAN", href: "/calendario", icon: <CalendarDays size={18} /> },
  { label: "Chatbot", href: "/chatbot", icon: <Bot size={18} /> },
];

const ADMIN_ITEMS: NavItem[] = [
  { label: "Administración", href: "/admin", icon: <Users size={18} />, adminOnly: true },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, clearSession } = useAuth();

  const isAdmin = user?.role === "owner" || user?.role === "admin";
  const isSuperadmin = user?.is_superadmin;

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    clearSession();
    router.push("/login");
    router.refresh();
  }

  return (
    <aside className="w-64 min-h-screen bg-brand-navy flex flex-col">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-white/10">
        <div className="text-2xl font-black tracking-tight">
          <span className="text-brand-orange">Tax</span>
          <span className="text-white">Ops</span>
        </div>
        <p className="text-slate-400 text-xs mt-0.5">Automatización Contable</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {/* Main */}
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.href} item={item} pathname={pathname} />
        ))}

        {/* Admin section */}
        {isAdmin && (
          <>
            <div className="pt-4 pb-1 px-3">
              <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider">
                Administración
              </p>
            </div>
            {ADMIN_ITEMS.map((item) => (
              <NavLink key={item.href} item={item} pathname={pathname} />
            ))}
          </>
        )}

        {/* Superadmin */}
        {isSuperadmin && (
          <>
            <div className="pt-4 pb-1 px-3">
              <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider">
                Superadmin
              </p>
            </div>
            <NavLink
              item={{ label: "Plataforma", href: "/superadmin", icon: <Shield size={18} /> }}
              pathname={pathname}
            />
          </>
        )}
      </nav>

      {/* Footer: user + logout */}
      <div className="px-3 py-4 border-t border-white/10 space-y-1">
        <Link
          href="/perfil"
          className={clsx(
            "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
            pathname === "/perfil"
              ? "bg-white/10 text-white"
              : "text-slate-300 hover:bg-white/5 hover:text-white"
          )}
        >
          <UserCircle size={18} />
          <div className="min-w-0">
            <p className="font-medium truncate">{user?.email ?? "Mi perfil"}</p>
            <p className="text-xs text-slate-400 capitalize">{user?.role}</p>
          </div>
        </Link>

        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-400 hover:bg-white/5 hover:text-white transition-colors"
        >
          <LogOut size={18} />
          Cerrar sesión
        </button>
      </div>
    </aside>
  );
}

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const active = pathname === item.href || pathname.startsWith(item.href + "/");
  return (
    <Link
      href={item.href}
      className={clsx(
        "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors group",
        active
          ? "bg-brand-orange text-white"
          : "text-slate-300 hover:bg-white/5 hover:text-white"
      )}
    >
      {item.icon}
      <span className="flex-1">{item.label}</span>
      {active && <ChevronRight size={14} />}
    </Link>
  );
}
