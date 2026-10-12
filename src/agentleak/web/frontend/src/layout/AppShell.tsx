// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react"
import { Link, NavLink, Outlet, useLocation } from "react-router-dom"
import {
  FlaskConical,
  FolderKanban,
  LayoutDashboard,
  Library,
  LogOut,
  Settings,
  ShieldCheck,
  UserCog,
} from "lucide-react"
import { api } from "@/lib/api"
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
import { AgentLeakLogo } from "@/features/AgentLeakLogo"

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/projects", label: "Projects", icon: FolderKanban, end: false },
  { to: "/playground", label: "Test lab", icon: FlaskConical, end: false },
  { to: "/scenarios", label: "Scenarios", icon: Library, end: false },
]

function isActivePath(pathname: string, to: string, end: boolean): boolean {
  return end ? pathname === to : pathname === to || pathname.startsWith(`${to}/`)
}

function sectionFor(pathname: string): { label: string; to: string } {
  const all = [
    ...NAV,
    { to: "/settings", label: "Settings", icon: Settings, end: false },
    { to: "/admin", label: "Administration", icon: UserCog, end: false },
  ]
  const match = all.find((n) => isActivePath(pathname, n.to, n.to === "/"))
  return match ? { label: match.label, to: match.to } : { label: "Dashboard", to: "/" }
}

function AppSidebar() {
  const { pathname } = useLocation()
  const { setOpenMobile } = useSidebar()
  const { user, logout } = useAuth()
  const [version, setVersion] = useState("")
  useEffect(() => {
    api.meta().then((m) => setVersion(m.version)).catch(() => {})
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
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="size-3.5 text-sev-ok" /> 100% local
              </span>
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
  const { pathname } = useLocation()
  const section = sectionFor(pathname)
  const isDetail = pathname !== section.to && pathname !== "/"

  return (
    <header className="platform-header sticky top-0 z-10 flex h-[52px] shrink-0 items-center gap-2 border-b border-border bg-background/90 backdrop-blur-sm">
      <div className="flex w-full items-center gap-2 px-4 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mr-1 h-4" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden sm:block">
              <BreadcrumbLink asChild>
                <Link to="/">AgentLeak</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:block" />
            <BreadcrumbItem>
              {isDetail ? (
                <BreadcrumbLink asChild>
                  <Link to={section.to}>{section.label}</Link>
                </BreadcrumbLink>
              ) : (
                <BreadcrumbPage>{section.label}</BreadcrumbPage>
              )}
            </BreadcrumbItem>
            {isDetail && (
              <>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage>Detail</BreadcrumbPage>
                </BreadcrumbItem>
              </>
            )}
          </BreadcrumbList>
        </Breadcrumb>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}

export function AppShell() {
  return (
    <SidebarProvider className="platform-shell">
      <AppSidebar />
      <SidebarInset className="platform-inset">
        <SiteHeader />
        <div className="platform-content flex flex-1 flex-col gap-4 p-4 lg:p-7">
          <div className="w-full">
            <Outlet />
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: React.ReactNode
}) {
  return (
    <div className="platform-page-header mb-7 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-[26px] font-normal leading-tight tracking-[-0.02em]">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions}
    </div>
  )
}
