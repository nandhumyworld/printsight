import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { formatCurrency, formatPercent } from '@/lib/utils';
import { BarChart3, FileText, Printer, TrendingDown, TrendingUp, AlertTriangle } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const PERIODS = [
  { label: '7 days', value: '7d' },
  { label: '30 days', value: '30d' },
  { label: '90 days', value: '90d' },
];

function StatCard({ title, value, sub, icon: Icon, color }: { title: string; value: string; sub?: string; icon: any; color: string }) {
  return (
    <div className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{title}</p>
        <div className={`rounded-full p-2 ${color}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <p className="mt-2 text-2xl font-bold">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const [period, setPeriod] = useState('30d');
  const navigate = useNavigate();

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['analytics-summary', period],
    queryFn: () => api.get(`/analytics/summary?period=${period}`).then(r => r.data.data),
  });

  const { data: trends, isLoading: trendsLoading } = useQuery({
    queryKey: ['analytics-trends', period],
    queryFn: () => api.get(`/analytics/trends?period=${period}`).then(r => r.data.data),
  });

  const { data: printers } = useQuery({
    queryKey: ['printers'],
    queryFn: () => api.get('/printers').then(r => r.data.data),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground text-sm mt-1">Print cost overview and trends</p>
        </div>
        <div className="flex gap-1 rounded-md border bg-card p-1">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`rounded px-3 py-1.5 text-sm transition-colors ${period === p.value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      {summaryLoading ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 rounded-lg border bg-card animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard
            title="Total Cost"
            value={formatCurrency(summary?.total_cost ?? 0)}
            sub={`${summary?.total_jobs ?? 0} jobs`}
            icon={BarChart3}
            color="bg-blue-100 text-blue-600"
          />
          <StatCard
            title="Total Pages"
            value={(summary?.total_pages ?? 0).toLocaleString()}
            sub={`Cost/page: ${formatCurrency(summary?.cost_per_page ?? 0)}`}
            icon={FileText}
            color="bg-green-100 text-green-600"
          />
          <StatCard
            title="Waste Cost"
            value={formatCurrency(summary?.waste_cost ?? 0)}
            sub={`${formatPercent(summary?.waste_pct ?? 0)} of total pages`}
            icon={AlertTriangle}
            color="bg-amber-100 text-amber-600"
          />
          <StatCard
            title="Color vs B&W"
            value={`${formatPercent(summary?.color_pct ?? 0)} color`}
            sub={`${(summary?.color_pages ?? 0).toLocaleString()} color / ${(summary?.bw_pages ?? 0).toLocaleString()} B&W`}
            icon={Printer}
            color="bg-purple-100 text-purple-600"
          />
        </div>
      )}

      {/* Trend Chart */}
      <div className="rounded-lg border bg-card p-5">
        <h2 className="mb-4 font-semibold">Cost Trend</h2>
        {trendsLoading ? (
          <div className="h-64 animate-pulse rounded bg-muted" />
        ) : trends && trends.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `₹${v}`} />
              <Tooltip formatter={(v: number) => formatCurrency(v)} />
              <Area type="monotone" dataKey="total_cost" name="Total Cost" stroke="hsl(var(--primary))" fill="hsl(var(--primary) / 0.1)" strokeWidth={2} />
              <Area type="monotone" dataKey="waste_cost" name="Waste Cost" stroke="hsl(var(--destructive))" fill="hsl(var(--destructive) / 0.1)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-64 items-center justify-center text-muted-foreground">
            <div className="text-center">
              <FileText className="mx-auto mb-2 h-10 w-10 opacity-30" />
              <p>No data yet. Upload a CSV log to get started.</p>
              {printers && printers.length > 0 && (
                <button onClick={() => navigate('/printers')} className="mt-2 text-sm text-primary hover:underline">
                  Go to Printers →
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Printers Quick View */}
      {printers && printers.length > 0 && (
        <div className="rounded-lg border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold">Printers</h2>
            <button onClick={() => navigate('/printers')} className="text-sm text-primary hover:underline">
              View all →
            </button>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {printers.slice(0, 6).map((p: any) => (
              <div
                key={p.id}
                onClick={() => navigate(`/printers/${p.id}`)}
                className="cursor-pointer rounded-md border p-3 hover:border-primary hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Printer className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium text-sm">{p.name}</span>
                  {!p.is_active && <span className="ml-auto rounded-full bg-destructive/10 px-2 py-0.5 text-xs text-destructive">Inactive</span>}
                </div>
                {p.model && <p className="mt-1 text-xs text-muted-foreground">{p.model}</p>}
                {p.location && <p className="text-xs text-muted-foreground">{p.location}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {printers && printers.length === 0 && (
        <div className="rounded-lg border-2 border-dashed p-10 text-center">
          <Printer className="mx-auto mb-3 h-12 w-12 text-muted-foreground/50" />
          <h3 className="font-semibold">No printers yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">Add your first printer to start tracking costs.</p>
          <button
            onClick={() => navigate('/printers/new')}
            className="mt-4 rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
          >
            Add Printer
          </button>
        </div>
      )}
    </div>
  );
}
