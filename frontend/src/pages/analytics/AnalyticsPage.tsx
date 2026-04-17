import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { formatCurrency, formatPercent } from '@/lib/utils';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
  PieChart, Pie, Cell,
} from 'recharts';
import { useState } from 'react';

const PERIODS = [
  { label: '7 days', value: '7d' },
  { label: '30 days', value: '30d' },
  { label: '90 days', value: '90d' },
];

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

export default function AnalyticsPage() {
  const [period, setPeriod] = useState('30d');

  const { data: comparison } = useQuery({
    queryKey: ['printers-comparison', period],
    queryFn: () => api.get(`/analytics/printers-comparison?period=${period}`).then(r => r.data.data),
  });

  const { data: breakdown } = useQuery({
    queryKey: ['cost-breakdown', period],
    queryFn: () => api.get(`/analytics/cost-breakdown?period=${period}`).then(r => r.data.data),
  });

  const { data: summary } = useQuery({
    queryKey: ['analytics-summary', period],
    queryFn: () => api.get(`/analytics/summary?period=${period}`).then(r => r.data.data),
  });

  const pieData = breakdown
    ? [
        { name: 'Paper', value: breakdown.paper_cost },
        { name: 'Toner', value: breakdown.toner_cost },
        { name: 'Waste', value: breakdown.waste_cost },
      ].filter((d) => d.value > 0)
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-sm text-muted-foreground mt-1">Cost breakdown and printer comparisons</p>
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

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Printer Comparison */}
        <div className="rounded-lg border bg-card p-5">
          <h2 className="font-semibold mb-4">Printer Cost Comparison</h2>
          {comparison && comparison.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={comparison}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="printer_name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `₹${v}`} />
                <Tooltip formatter={(v: number) => formatCurrency(v)} />
                <Bar dataKey="total_cost" name="Total Cost" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-muted-foreground text-sm">No data for this period</div>
          )}
        </div>

        {/* Cost Breakdown Pie */}
        <div className="rounded-lg border bg-card p-5">
          <h2 className="font-semibold mb-4">Cost Breakdown</h2>
          {pieData.length > 0 ? (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="60%" height={220}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatCurrency(v)} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-3">
                {pieData.map((d, i) => (
                  <div key={d.name} className="flex items-center gap-2">
                    <div className="h-3 w-3 rounded-sm" style={{ background: COLORS[i % COLORS.length] }} />
                    <div>
                      <p className="text-sm font-medium">{d.name}</p>
                      <p className="text-xs text-muted-foreground">{formatCurrency(d.value)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-muted-foreground text-sm">No cost data yet</div>
          )}
        </div>
      </div>

      {/* Printer Details Table */}
      {comparison && comparison.length > 0 && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="px-5 py-4 border-b">
            <h2 className="font-semibold">Printer Details</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 text-left">Printer</th>
                  <th className="px-4 py-3 text-right">Jobs</th>
                  <th className="px-4 py-3 text-right">Pages</th>
                  <th className="px-4 py-3 text-right">Total Cost</th>
                  <th className="px-4 py-3 text-right">Cost/Page</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {comparison.map((p: any) => (
                  <tr key={p.printer_id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium">{p.printer_name}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">{p.total_jobs}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">{p.total_pages.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatCurrency(p.total_cost)}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">{formatCurrency(p.cost_per_page)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
