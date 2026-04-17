import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Shield, Users, Printer, FileText, RefreshCw } from 'lucide-react';
import { NavLink } from 'react-router-dom';

interface AdminStats {
  users: { total: number; active: number; inactive: number; owners: number; print_persons: number };
  printers: { total: number; active: number; inactive: number };
  activity: { total_jobs: number; total_uploads: number; total_toner_replacements: number };
}

function StatCard({ label, value, sub, icon: Icon, color = 'text-foreground' }: {
  label: string; value: number | string; sub?: string; icon: React.ElementType; color?: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-5 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{label}</p>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <p className={`text-3xl font-bold ${color}`}>{typeof value === 'number' ? value.toLocaleString() : value}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

export default function AdminPage() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: () => api.get('/admin/stats').then(r => r.data.data as AdminStats),
  });

  return (
    <div className="max-w-5xl space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6 text-primary" />
            Admin Panel
          </h1>
          <p className="text-sm text-muted-foreground mt-1">System overview and management</p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-28 rounded-lg border bg-muted animate-pulse" />
          ))}
        </div>
      ) : data ? (
        <>
          {/* Users section */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold flex items-center gap-2">
                <Users className="h-4 w-4" /> Users
              </h2>
              <NavLink to="/admin/users" className="text-sm text-primary hover:underline">
                Manage users →
              </NavLink>
            </div>
            <div className="grid grid-cols-4 gap-4">
              <StatCard label="Total Users" value={data.users.total} icon={Users} />
              <StatCard label="Active" value={data.users.active} icon={Users} color="text-green-600" sub="can log in" />
              <StatCard label="Inactive" value={data.users.inactive} icon={Users} color={data.users.inactive > 0 ? 'text-red-600' : 'text-foreground'} sub="suspended" />
              <div className="rounded-lg border bg-card p-5 space-y-2">
                <p className="text-sm text-muted-foreground">Roles</p>
                <div className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span>Owners</span>
                    <span className="font-medium">{data.users.owners}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Print Persons</span>
                    <span className="font-medium">{data.users.print_persons}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Printers section */}
          <div>
            <h2 className="font-semibold flex items-center gap-2 mb-3">
              <Printer className="h-4 w-4" /> Printers
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <StatCard label="Total Printers" value={data.printers.total} icon={Printer} />
              <StatCard label="Active" value={data.printers.active} icon={Printer} color="text-green-600" />
              <StatCard label="Inactive" value={data.printers.inactive} icon={Printer} color={data.printers.inactive > 0 ? 'text-yellow-600' : 'text-foreground'} />
            </div>
          </div>

          {/* Activity section */}
          <div>
            <h2 className="font-semibold flex items-center gap-2 mb-3">
              <FileText className="h-4 w-4" /> System Activity
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <StatCard label="Total Print Jobs" value={data.activity.total_jobs} icon={FileText} sub="across all printers" />
              <StatCard label="CSV Uploads" value={data.activity.total_uploads} icon={FileText} sub="batches processed" />
              <StatCard label="Toner Replacements" value={data.activity.total_toner_replacements} icon={FileText} sub="logged events" />
            </div>
          </div>
        </>
      ) : (
        <div className="rounded-lg border p-8 text-center text-muted-foreground">Failed to load stats</div>
      )}

      {/* Quick links */}
      <div className="rounded-lg border bg-card p-5">
        <h2 className="font-semibold mb-3">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <NavLink
            to="/admin/users"
            className="rounded-md border px-4 py-2 text-sm hover:bg-muted transition-colors flex items-center gap-2"
          >
            <Users className="h-4 w-4" />
            Manage Users
          </NavLink>
          <NavLink
            to="/printers"
            className="rounded-md border px-4 py-2 text-sm hover:bg-muted transition-colors flex items-center gap-2"
          >
            <Printer className="h-4 w-4" />
            View All Printers
          </NavLink>
          <NavLink
            to="/reports/toner-yield"
            className="rounded-md border px-4 py-2 text-sm hover:bg-muted transition-colors flex items-center gap-2"
          >
            <FileText className="h-4 w-4" />
            Toner Yield Report
          </NavLink>
        </div>
      </div>
    </div>
  );
}
