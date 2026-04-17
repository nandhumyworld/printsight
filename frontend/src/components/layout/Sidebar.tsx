import { NavLink } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard, BarChart3, Printer, FileText, Settings,
  ChevronDown, Shield, Tally5,
} from 'lucide-react';
import React, { useState } from 'react';

interface NavItem { label: string; to: string; icon: React.ElementType; ownerOnly?: boolean; }
interface NavGroup { label: string; icon: React.ElementType; items: NavItem[]; }

const navGroups: NavGroup[] = [
  {
    label: 'Overview',
    icon: LayoutDashboard,
    items: [
      { label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
      { label: 'Analytics', to: '/analytics', icon: BarChart3, ownerOnly: true },
    ],
  },
  {
    label: 'Printers',
    icon: Printer,
    items: [{ label: 'All Printers', to: '/printers', icon: Printer }],
  },
  {
    label: 'Reports',
    icon: FileText,
    items: [
      { label: 'Cost Reports', to: '/reports', icon: FileText, ownerOnly: true },
      { label: 'Toner Yield', to: '/reports/toner-yield', icon: Tally5, ownerOnly: true },
    ],
  },
  {
    label: 'Settings',
    icon: Settings,
    items: [
      { label: 'Paper & Ink Costs', to: '/settings/costs', icon: Settings, ownerOnly: true },
      { label: 'Toner Replacements', to: '/settings/toner-replacements', icon: Settings },
      { label: 'Notifications', to: '/settings/notifications', icon: Settings, ownerOnly: true },
      { label: 'Webhooks', to: '/settings/webhooks', icon: Settings, ownerOnly: true },
    ],
  },
];

export function Sidebar() {
  const { hasRole } = useAuth();
  const isOwner = hasRole('owner');
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggle = (label: string) => setCollapsed((p) => ({ ...p, [label]: !p[label] }));

  return (
    <aside className="flex w-60 flex-col border-r bg-card">
      <div className="flex h-16 items-center gap-2 border-b px-4">
        <Printer className="h-6 w-6 text-primary" />
        <span className="text-lg font-bold">PrintSight</span>
      </div>
      <nav className="flex-1 overflow-y-auto py-4">
        {navGroups.map((group) => {
          const visibleItems = group.items.filter((i) => !i.ownerOnly || isOwner);
          if (!visibleItems.length) return null;
          const isOpen = !collapsed[group.label];
          return (
            <div key={group.label} className="mb-1">
              <button
                onClick={() => toggle(group.label)}
                className="flex w-full items-center justify-between px-4 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground"
              >
                <span>{group.label}</span>
                <ChevronDown className={cn('h-3 w-3 transition-transform', isOpen && 'rotate-180')} />
              </button>
              {isOpen && visibleItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn('flex items-center gap-3 px-4 py-2 text-sm transition-colors',
                      isActive ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:bg-muted hover:text-foreground')
                  }
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          );
        })}
        {isOwner && (
          <div className="mt-4 border-t pt-4">
            <NavLink
              to="/admin"
              end
              className={({ isActive }) =>
                cn('flex items-center gap-3 px-4 py-2 text-sm transition-colors',
                  isActive ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:bg-muted hover:text-foreground')
              }
            >
              <Shield className="h-4 w-4" />
              Admin Panel
            </NavLink>
            <NavLink
              to="/admin/users"
              className={({ isActive }) =>
                cn('flex items-center gap-3 pl-10 pr-4 py-2 text-sm transition-colors',
                  isActive ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:bg-muted hover:text-foreground')
              }
            >
              User Management
            </NavLink>
          </div>
        )}
      </nav>
    </aside>
  );
}
