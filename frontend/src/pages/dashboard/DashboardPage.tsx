import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart3, FileText, Printer, AlertTriangle } from 'lucide-react';
import { api } from '@/services/api';
import { formatCurrency, formatPercent } from '@/lib/utils';
import { usePrinter } from '@/context/PrinterContext';
import { KpiCard } from '@/components/charts/KpiCard';
import { DateRangePicker, DateRange } from '@/components/ui/DateRangePicker';
import { StackedCostAreaChart } from '@/components/charts/StackedCostAreaChart';
import { PaperDonut3D } from '@/components/charts/PaperDonut3D';
import { TonerBreakdownBar } from '@/components/charts/TonerBreakdownBar';
import { JobDetailDrawer } from '@/components/charts/JobDetailDrawer';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

function defaultStart(): Date {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d;
}

function aggregateTotals(rows: any[]): { color: string; cost: number }[] {
  const totals: Record<string, number> = {};
  rows.forEach(r =>
    Object.entries(r).forEach(([k, v]) => {
      if (k === 'bucket' || typeof v !== 'number') return;
      totals[k] = (totals[k] || 0) + (v as number);
    })
  );
  return Object.entries(totals)
    .filter(([k]) => k !== 'paper' && k !== 'total_cost' && k !== 'paper_cost' && k !== 'toner_cost' && k !== 'waste_cost' && k !== 'pages' && k !== 'jobs')
    .map(([color, cost]) => ({ color, cost }))
    .filter(d => d.cost > 0)
    .sort((a, b) => b.cost - a.cost);
}

const EmptyState = ({ message = "No data in the selected range." }: { message?: string }) => (
  <div className="flex h-64 items-center justify-center text-muted-foreground">
    <div className="text-center">
      <FileText className="mx-auto mb-2 h-10 w-10 opacity-30" />
      <p className="text-sm">{message}</p>
    </div>
  </div>
);

export default function DashboardPage() {
  const [range, setRange] = useState<DateRange>({ start: defaultStart(), end: new Date() });
  const [selectedJob, setSelectedJob] = useState<any | null>(null);
  const [selectedPaperTypes, setSelectedPaperTypes] = useState<string[]>([]);
  const [paperDropdownOpen, setPaperDropdownOpen] = useState(false);
  const navigate = useNavigate();
  const { selectedPrinter } = usePrinter();

  const printerParam = selectedPrinter ? `&printer_id=${selectedPrinter.id}` : '';
  const rp = `start_date=${range.start.toISOString()}&end_date=${range.end.toISOString()}${printerParam}`;

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['analytics-summary', rp],
    queryFn: () => api.get(`/analytics/summary?${rp}`).then(r => r.data.data),
  });

  const { data: tonerData, isLoading: tonerLoading } = useQuery({
    queryKey: ['toner-breakdown', rp],
    queryFn: () => api.get(`/analytics/toner-breakdown?${rp}`).then(r => r.data.data),
  });

  const { data: paperData, isLoading: paperLoading } = useQuery({
    queryKey: ['paper-breakdown', rp],
    queryFn: () => api.get(`/analytics/paper-breakdown?${rp}`).then(r => r.data.data),
  });

  const { data: topJobs } = useQuery({
    queryKey: ['top-jobs', rp],
    queryFn: () => api.get(`/analytics/top-jobs?${rp}&limit=10`).then(r => r.data.data),
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

      {/* Header + date range */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground text-sm mt-1">Print cost overview and trends</p>
        </div>
        <DateRangePicker value={range} onChange={setRange} />
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
            title="Paper Cost"
            value={formatCurrency(summary?.paper_cost ?? 0)}
            sub={`Toner: ${formatCurrency(summary?.toner_cost ?? 0)}`}
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

      {/* Stacked cost area chart */}
      <div className="rounded-xl border bg-card p-5">
        <h2 className="mb-4 font-semibold">Cost over time — Paper + Toner colors (stacked)</h2>
        {tonerLoading ? (
          <div className="h-64 animate-pulse rounded bg-muted" />
        ) : tonerData && tonerData.length > 0 ? (
          <StackedCostAreaChart data={tonerData} />
        ) : (
          <EmptyState message="No data yet. Upload a CSV log to get started." />
        )}
      </div>

      {/* Paper donut + Toner bar */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border bg-card p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="font-semibold">Paper cost by type</h2>
            {!paperLoading && paperData && paperData.length > 0 && (
              <div className="relative">
                <button
                  onClick={() => setPaperDropdownOpen(v => !v)}
                  className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs hover:bg-muted/50"
                >
                  {selectedPaperTypes.length === 0
                    ? 'Select types...'
                    : `${selectedPaperTypes.length} selected`}
                  <svg className={`h-3 w-3 transition-transform ${paperDropdownOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </button>
                {paperDropdownOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setPaperDropdownOpen(false)} />
                    <div className="absolute right-0 top-full z-20 mt-1 max-h-60 w-56 overflow-y-auto rounded-md border bg-card shadow-lg">
                      <div className="sticky top-0 border-b bg-card p-2">
                        <button
                          onClick={() => {
                            setSelectedPaperTypes(paperData.map((d: any) => d.paper_type));
                            setPaperDropdownOpen(false);
                          }}
                          className="w-full rounded px-2 py-1 text-left text-xs font-medium hover:bg-muted/50"
                        >
                          Select all
                        </button>
                        <button
                          onClick={() => { setSelectedPaperTypes([]); setPaperDropdownOpen(false); }}
                          className="w-full rounded px-2 py-1 text-left text-xs font-medium hover:bg-muted/50"
                        >
                          Clear selection
                        </button>
                      </div>
                      {paperData.map((d: any) => (
                        <label
                          key={d.paper_type}
                          className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted/30"
                        >
                          <input
                            type="checkbox"
                            checked={selectedPaperTypes.includes(d.paper_type)}
                            onChange={() => {
                              setSelectedPaperTypes(prev =>
                                prev.includes(d.paper_type)
                                  ? prev.filter(t => t !== d.paper_type)
                                  : [...prev, d.paper_type],
                              );
                            }}
                            className="rounded"
                          />
                          <span className="truncate">{d.paper_type}</span>
                        </label>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
          {paperLoading ? (
            <div className="h-64 animate-pulse rounded bg-muted" />
          ) : selectedPaperTypes.length > 0 && paperData ? (
            <PaperDonut3D data={paperData.filter((d: any) => selectedPaperTypes.includes(d.paper_type))} />
          ) : paperData && paperData.length > 0 ? (
            <div className="flex h-64 items-center justify-center text-muted-foreground">
              <p className="text-sm">Select paper types from the dropdown above to compare costs.</p>
            </div>
          ) : (
            <EmptyState />
          )}
        </div>
        <div className="rounded-xl border bg-card p-5">
          <h2 className="mb-4 font-semibold">Toner cost by color</h2>
          {tonerLoading ? (
            <div className="h-64 animate-pulse rounded bg-muted" />
          ) : tonerData && aggregateTotals(tonerData).length > 0 ? (
            <TonerBreakdownBar data={aggregateTotals(tonerData)} />
          ) : (
            <EmptyState />
          )}
        </div>
      </div>

      {/* Top jobs */}
      <div className="rounded-xl border bg-card p-5">
        <h2 className="mb-4 font-semibold">Top 10 most expensive jobs</h2>
        {topJobs && topJobs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-4">Job</th>
                  <th className="pb-2 pr-4">Paper</th>
                  <th className="pb-2 pr-4 text-right">Pages</th>
                  <th className="pb-2 pr-4 text-right">Paper</th>
                  <th className="pb-2 pr-4 text-right">Toner</th>
                  <th className="pb-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {topJobs.map((j: any) => (
                  <tr
                    key={j.id}
                    onClick={() => setSelectedJob(j)}
                    className="cursor-pointer border-b last:border-0 hover:bg-muted/50 transition-colors"
                  >
                    <td className="py-2 pr-4 font-medium">{j.job_name || j.job_id}</td>
                    <td className="py-2 pr-4 text-muted-foreground text-xs">{j.paper_type || '—'}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{j.printed_pages}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">₹{j.paper_cost.toFixed(2)}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">₹{j.toner_cost.toFixed(2)}</td>
                    <td className="py-2 text-right tabular-nums font-semibold">₹{j.total_cost.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState />
        )}
      </div>

      <JobDetailDrawer job={selectedJob} onClose={() => setSelectedJob(null)} />
    </div>
  );
}
