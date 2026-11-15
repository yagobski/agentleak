// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { Fragment, useEffect, useState } from "react"
import { Link, NavLink, Outlet, useLocation } from "react-router-dom"
import {
  FolderKanban,
  LayoutDashboard,
  Library,
  LogOut,
  Rows3,
  ScanSearch,
  Settings,
  Swords,
  UserCog,
} from "lucide-react"
import { loadMeta } from "@/lib/meta"
import { useAuth } from "@/lib/auth"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar"
import { ThemeToggle } from "@/features/ThemeToggle"
import { cn } from "@/lib/utils"
import { AgentLeakLogo } from "@/features/AgentLeakLogo"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { CrumbProvider, useCrumbState, useCrumbs, type Crumb } from "./crumbs"

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/analyze", label: "Analyze a trace", icon: ScanSearch, end: false },
  { to: "/runs", label: "Runs", icon: Rows3, end: false },
  { to: "/projects", label: "Projects", icon: FolderKanban, end: false },
  { to: "/scenarios", label: "Scenarios", icon: Library, end: false },
  { to: "/playground", label: "Red team", icon: Swords, end: false },
]

function isActivePath(pathname: string, to: string, end: boolean): boolean {
  return end ? pathname === to : pathname === to || pathname.startsWith(`${to}/`)
}

function AppSidebar() {
  const { pathname } = useLocation()
  const { setOpenMobile } = useSidebar()
  const { user, logout } = useAuth()
  const [version, setVersion] = useState("")
  useEffect(() => {
    loadMeta().then((m) => setVersion(m.version)).catch(() => {})
  }, [])
  useEffect(() => {
    setOpenMobile(false)
  }, [pathname, setOpenMobile])

  return (
    <Sidebar collapsible="icon" variant="sidebar" className="platform-sidebar">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="AgentLeak">
              <Link to="/">
                <div className="platform-brand">
                  <AgentLeakLogo className="agentleak-logo-platform" label="AgentLeak platform" />
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Platform</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV.map((item) => (
                <SidebarMenuItem key={item.to}>
                  <SidebarMenuButton asChild isActive={isActivePath(pathname, item.to, item.end)} tooltip={item.label}>
                    <NavLink to={item.to} end={item.end}>
                      <item.icon />
                      <span>{item.label}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          {user?.is_admin && (
            <SidebarMenuItem>
              <SidebarMenuButton asChild isActive={isActivePath(pathname, "/admin", false)} tooltip="Administration">
                <NavLink to="/admin">
                  <UserCog />
                  <span>Administration</span>
                </NavLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )}
          <SidebarMenuItem>
            <SidebarMenuButton asChild isActive={isActivePath(pathname, "/settings", false)} tooltip="Settings">
              <NavLink to="/settings">
                <Settings />
                <span>Settings</span>
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
          {user && (
            <SidebarMenuItem>
              <SidebarMenuButton tooltip={`Sign out (${user.email})`} onClick={() => void logout()}>
                <LogOut />
                <span className="truncate">{user.name || user.email}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )}
          <SidebarMenuItem>
            <div className="flex items-center justify-between gap-2 px-2 py-1.5 text-[11px] text-muted-foreground group-data-[collapsible=icon]:hidden">
              <span>Runs on this machine</span>
              {version && <span className="font-mono">v{version}</span>}
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

function SiteHeader() {
  const crumbs = useCrumbState()
  return (
    <header className="platform-header sticky top-0 z-10 flex h-[52px] shrink-0 items-center gap-2 border-b border-border">
      <div className="flex w-full min-w-0 items-center gap-2 px-4 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mr-1 h-4" />
        <Breadcrumb className="min-w-0 flex-1">
          <BreadcrumbList className="flex-nowrap">
            {crumbs.map((c, i) => {
              const last = i === crumbs.length - 1
              return (
                <Fragment key={`${i}-${c.label}`}>
                  {i > 0 && <BreadcrumbSeparator className={last ? "" : "hidden sm:block"} />}
                  <BreadcrumbItem className={cn("min-w-0", !last && "hidden sm:inline-flex")}>
                    {last || !c.to ? (
                      <BreadcrumbPage className="truncate">{c.label}</BreadcrumbPage>
                    ) : (
                      <BreadcrumbLink asChild>
                        <Link to={c.to} className="max-w-[16rem] truncate">
                          {c.label}
                        </Link>
                      </BreadcrumbLink>
                    )}
                  </BreadcrumbItem>
                </Fragment>
              )
            })}
          </BreadcrumbList>
        </Breadcrumb>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}

function Footer() {
  const [version, setVersion] = useState("")
  useEffect(() => {
    loadMeta().then((m) => setVersion(m.version)).catch(() => {})
  }, [])
  return (
    <footer className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border px-4 py-3 text-[11px] text-muted-foreground lg:px-7">
      <span>
        AgentLeak <span className="font-mono">{version ? `v${version}` : ""}</span>
      </span>
      <span>Local workspace: traces and reports stay on this machine.</span>
      <a className="underline-offset-2 hover:text-foreground hover:underline" href="/api/docs">
        API reference
      </a>
      <a className="underline-offset-2 hover:text-foreground hover:underline" href="/api/schemas">
        JSON schemas
      </a>
      <span className="ml-auto hidden lg:inline">
        Press <kbd className="rounded border border-border px-1 font-mono">/</kbd> to search the current table
      </span>
    </footer>
  )
}

/** "/" focuses the page's main search field, as in most data tools. */
function useSlashToSearch() {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return
      const t = e.target as HTMLElement | null
      if (t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName))) return
      const field = document.querySelector<HTMLInputElement>('[data-shortcut="search"]')
      if (field) {
        e.preventDefault()
        field.focus()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])
}

export function AppShell() {
  const { pathname } = useLocation()
  useSlashToSearch()
  return (
    <CrumbProvider>
      <SidebarProvider className="platform-shell">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-background focus:px-3 focus:py-2 focus:text-sm focus:ring-2 focus:ring-ring"
        >
          Skip to content
        </a>
        <AppSidebar />
        <SidebarInset className="platform-inset min-w-0">
          <SiteHeader />
          <main id="main" className="platform-content flex min-w-0 flex-1 flex-col p-4 lg:p-7">
            <ErrorBoundary key={pathname}>
              <Outlet />
            </ErrorBoundary>
          </main>
          <Footer />
        </SidebarInset>
      </SidebarProvider>
    </CrumbProvider>
  )
}

export function PageHeader({
  title,
  description,
  actions,
  crumbs,
}: {
  title: string
  description?: React.ReactNode
  actions?: React.ReactNode
  /** Breadcrumb trail; defaults to the title alone. */
  crumbs?: Crumb[]
}) {
  useCrumbs(crumbs ?? [{ label: title }])
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-border pb-4">
      <div className="min-w-0">
        <h1 className="break-words text-[22px] font-medium leading-tight tracking-[-0.01em]">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
