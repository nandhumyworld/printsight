import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { formatCurrency, formatPercent } from '@/lib/utils';
import { BarChart3, FileText, Printer, AlertTriangle } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { KpiCard } from '@/components/charts/KpiCard';
import { CostBreakdownChart } from '@/components/charts/CostBreakdownChart';
import { usePrinter } from '@/context/PrinterContext';

const PERIODS = [
  { label: 'Day',   value: '1d' },
  { label: 'Week',  value: '7d' },
  { label: 'Month', value: '30d' },
  { label: 'Year',  value: '365d' },
];

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

export default function DashboardPage() {
  const [period, setPeriod] = useState('30d');
  const navigate = useNavigate();
  const { selectedPrinter } = usePrinter();

  const printerParam = selectedPrinter ? `&printer_id=${selectedPrinter.id}` : '';

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['analytics-summary', period, selectedPrinter?.id],
    queryFn: () => api.get(`/analytics/summary?period=${period}${printerParam}`).then(r => r.data.data),
  });

  const { data: trends, isLoading: trendsLoading } = useQuery({
    queryKey: ['analytics-trends', period, selectedPrinter?.id],
    queryFn: () => api.get(`/analytics/trends?period=${period}${printerParam}`).then(r => r.data.data),
  });

  const heroImage = selectedPrinter?.image_url
    ? `${API_BASE}${selectedPrinter.image_url}`
    : null;

  return (
    <div className="space-y-6">
      {/* Hero banner */}
      {selectedPrinter && (
        <div
          className="relative flex h-28 items-end overflow-hidden rounded-xl bg-gradient-to-r from-slate-800 to-slate-600 px-6 pb-4 shadow-sm"
          style={heroImage ? { backgroundImage: `url(${heroImage})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}}
        >
          <div className="absolute inset-0 bg-black/40 rounded-xl" />
          <div className="relative z-10">
            <p className="text-xs font-medium text-white/70 uppercase tracking-wide">Selected Printer</p>
            <h2 className="text-xl font-bold text-white">{selectedPrinter.name}</h2>
            {selectedPrinter.model && <p className="text-sm text-white/70">{selectedPrinter.model}</p>}
          </div>
          <button
            onClick={() => navigate(`/printers/${selectedPrinter.id}`)}
            className="relative z-10 ml-auto rounded-md bg-white/20 px-3 py-1.5 text-xs font-medium text-white hover:bg-white/30 transition-colors"
          >
            Manage →
          </button>
        </div>
      )}

      {/* Header */}
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

      {/* KPI cards */}
      {summaryLoading ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-28 rounded-xl animate-pulse bg-muted" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <KpiCard
            title="Total Cost"
            value={formatCurrency(summary?.total_cost ?? 0)}
            sub={`${summary?.total_jobs ?? 0} jobs`}
            icon={BarChart3}
            gradient="from-blue-500 to-cyan-400"
          />
          <KpiCard
            title="Total Pages"
            value={(summary?.total_pages ?? 0).toLocaleString()}
            sub={`₹${(summary?.cost_per_page ?? 0).toFixed(4)}/page`}
            icon={FileText}
            gradient="from-violet-500 to-purple-400"
          />
          <KpiCard
            title="Waste Cost"
            value={formatCurrency(summary?.waste_cost ?? 0)}
            sub={`${formatPercent(summary?.waste_pct ?? 0)} of pages`}
            icon={AlertTriangle}
            gradient="from-amber-500 to-orange-400"
          />
          <KpiCard
            title="Color vs B&W"
            value={`${formatPercent(summary?.color_pct ?? 0)} color`}
            sub={`${(summary?.color_pages ?? 0).toLocaleString()} color / ${(summary?.bw_pages ?? 0).toLocaleString()} B&W`}
            icon={Printer}
            gradient="from-emerald-500 to-teal-400"
          />
        </div>
      )}

      {/* Cost breakdown grouped bar */}
      <div className="rounded-xl border bg-card p-5">
        <h2 className="mb-4 font-semibold">Paper vs Toner Cost</h2>
        {trendsLoading ? (
          <div className="h-64 animate-pulse rounded bg-muted" />
        ) : trends && trends.length > 0 ? (
          <CostBreakdownChart data={trends} />
        ) : (
          <div className="flex h-64 items-center justify-center text-muted-foreground">
            <div className="text-center">
              <FileText className="mx-auto mb-2 h-10 w-10 opacity-30" />
              <p>No data yet. Upload a CSV log to get started.</p>
            </div>
          </div>
        )}
      </div>

      {/* Cost trend area chart */}
      <div className="rounded-xl border bg-card p-5">
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
              <Area type="monotone" dataKey="waste_cost" name="Waste Cost" stroke="#f97316" fill="rgba(249,115,22,0.1)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        ) : null}
      </div>
    </div>
  );
}
