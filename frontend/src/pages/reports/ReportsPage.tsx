import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { formatDateTime, formatPercent } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import { Download, Search, FileText, ChevronLeft, ChevronRight } from 'lucide-react';

const STATUS_OPTIONS = ['all', 'completed', 'failed', 'cancelled'];
const SORT_OPTIONS = [
  { label: 'Date (newest)', value: 'recorded_at_desc' },
  { label: 'Date (oldest)', value: 'recorded_at_asc' },
  { label: 'Pages (high)', value: 'printed_pages_desc' },
  { label: 'Pages (low)', value: 'printed_pages_asc' },
  { label: 'Job Name', value: 'job_name_asc' },
];
const PIE_COLORS: Record<string, string> = {
  completed: '#22c55e',
  failed: '#ef4444',
  cancelled: '#f59e0b',
  unknown: '#94a3b8',
};

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-bold">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

export default function ReportsPage() {
  const [filters, setFilters] = useState({
    printer_ids: '',
    date_from: '',
    date_to: '',
    status: 'all',
    search: '',
    sort: 'recorded_at_desc',
    page: 1,
    per_page: 50,
  });
  const [pendingSearch, setPendingSearch] = useState('');
  const [exporting, setExporting] = useState(false);

  const { data: printersData } = useQuery({
    queryKey: ['printers'],
    queryFn: () => api.get('/printers').then(r => r.data.data),
  });

  const [sort_by, sort_dir] = filters.sort.split('_').reduce<[string, string]>((acc, part, idx, arr) => {
    if (idx === arr.length - 1) return [arr.slice(0, -1).join('_'), part];
    return acc;
  }, ['recorded_at', 'desc']);

  const queryParams = {
    printer_ids: filters.printer_ids || undefined,
    date_from: filters.date_from || undefined,
    date_to: filters.date_to || undefined,
    status: filters.status,
    search: filters.search || undefined,
    page: filters.page,
    per_page: filters.per_page,
    sort_by,
    sort_dir,
  };

  const { data, isLoading } = useQuery({
    queryKey: ['reports-jobs', filters],
    queryFn: () => {
      const params = new URLSearchParams();
      Object.entries(queryParams).forEach(([k, v]) => { if (v !== undefined) params.set(k, String(v)); });
      return api.get(`/reports/jobs?${params}`).then(r => r.data.data);
    },
  });

  const summary = data?.summary;
  const jobs: any[] = data?.jobs ?? [];
  const total: number = data?.total ?? 0;
  const totalPages = Math.ceil(total / filters.per_page);

  // Charts derived client-side from current page's jobs
  const dayGroups = useMemo(() => {
    const map: Record<string, number> = {};
    jobs.forEach(j => {
      if (!j.recorded_at) return;
      const day = j.recorded_at.slice(0, 10);
      map[day] = (map[day] ?? 0) + j.printed_pages;
    });
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b)).map(([date, pages]) => ({ date, pages }));
  }, [jobs]);

  const statusGroups = useMemo(() => {
    const map: Record<string, number> = {};
    jobs.forEach(j => {
      const s = j.status || 'unknown';
      map[s] = (map[s] ?? 0) + 1;
    });
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [jobs]);

  const set = (field: string) => (value: string | number) =>
    setFilters(f => ({ ...f, [field]: value, page: field !== 'page' ? 1 : (value as number) }));

  const handleApply = () => set('search')(pendingSearch);

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (filters.printer_ids) params.set('printer_ids', filters.printer_ids);
      if (filters.date_from) params.set('date_from', filters.date_from);
      if (filters.date_to) params.set('date_to', filters.date_to);
      if (filters.status !== 'all') params.set('status', filters.status);
      if (filters.search) params.set('search', filters.search);
      const response = await api.get(`/reports/jobs/export?${params}`, { responseType: 'blob' });
      const url = URL.createObjectURL(response.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `printsight-report-${filters.date_from || 'all'}-to-${filters.date_to || 'now'}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Reports</h1>
          <p className="text-sm text-muted-foreground mt-1">Filter, analyse and export print job logs</p>
        </div>
        <Button onClick={handleExport} isLoading={exporting} variant="outline">
          <Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>
      </div>

      {/* Filter Bar */}
      <div className="rounded-lg border bg-card p-4">
        <div className="flex flex-wrap gap-3">
          {/* Printer filter */}
          <select
            value={filters.printer_ids}
            onChange={e => set('printer_ids')(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm min-w-[160px]"
          >
            <option value="">All Printers</option>
            {printersData?.map((p: any) => (
              <option key={p.id} value={String(p.id)}>{p.name}</option>
            ))}
          </select>

          {/* Date range */}
          <input
            type="date"
            value={filters.date_from}
            onChange={e => set('date_from')(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="From"
          />
          <input
            type="date"
            value={filters.date_to}
            onChange={e => set('date_to')(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="To"
          />

          {/* Status */}
          <select
            value={filters.status}
            onChange={e => set('status')(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {STATUS_OPTIONS.map(s => (
              <option key={s} value={s}>{s === 'all' ? 'All Statuses' : s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>

          {/* Sort */}
          <select
            value={filters.sort}
            onChange={e => set('sort')(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          {/* Search */}
          <div className="flex gap-2 flex-1 min-w-[200px]">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search job, owner..."
                value={pendingSearch}
                onChange={e => setPendingSearch(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleApply()}
                className="pl-8"
              />
            </div>
            <Button onClick={handleApply} size="sm">Apply</Button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <StatCard label="Total Jobs" value={summary.total_jobs.toLocaleString()} />
          <StatCard label="Total Pages" value={summary.total_pages.toLocaleString()} />
          <StatCard label="Color Pages" value={summary.color_pages.toLocaleString()} sub={`${formatPercent(summary.total_pages ? summary.color_pages / summary.total_pages * 100 : 0)} of total`} />
          <StatCard label="B&W Pages" value={summary.bw_pages.toLocaleString()} />
          <StatCard label="Waste" value={`${summary.waste_pages.toLocaleString()} pages`} sub={`${formatPercent(summary.waste_pct)} waste rate`} />
        </div>
      )}

      {/* Charts */}
      {jobs.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Jobs per day bar chart */}
          <div className="rounded-lg border bg-card p-5">
            <h2 className="font-semibold mb-4">Pages per Day (current page)</h2>
            {dayGroups.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={dayGroups}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="pages" name="Pages" fill="hsl(var(--primary))" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-muted-foreground text-sm">No dated jobs</div>
            )}
          </div>

          {/* Status pie */}
          <div className="rounded-lg border bg-card p-5">
            <h2 className="font-semibold mb-4">Status Breakdown (current page)</h2>
            {statusGroups.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={statusGroups} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {statusGroups.map((entry, i) => (
                      <Cell key={i} fill={PIE_COLORS[entry.name] ?? '#94a3b8'} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-muted-foreground text-sm">No data</div>
            )}
          </div>
        </div>
      )}

      {/* Jobs Table */}
      <div className="rounded-lg border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b flex items-center justify-between">
          <h2 className="font-semibold">Print Jobs</h2>
          <span className="text-xs text-muted-foreground">
            {isLoading ? 'Loading...' : `${total.toLocaleString()} total · page ${filters.page} of ${totalPages || 1}`}
          </span>
        </div>

        {isLoading ? (
          <div className="p-8 text-center">
            <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground">
            <FileText className="mx-auto mb-3 h-10 w-10 opacity-30" />
            <p>No jobs match the current filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-left">Job ID</th>
                  <th className="px-4 py-3 text-left">Job Name</th>
                  <th className="px-4 py-3 text-left">Owner</th>
                  <th className="px-4 py-3 text-right">Pages</th>
                  <th className="px-4 py-3 text-right">Color</th>
                  <th className="px-4 py-3 text-right">B&W</th>
                  <th className="px-4 py-3 text-left">Paper</th>
                  <th className="px-4 py-3 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {jobs.map((j: any) => (
                  <tr key={j.id} className={`hover:bg-muted/30 ${j.is_waste ? 'bg-red-50/30' : ''}`}>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">
                      {j.recorded_at ? formatDateTime(j.recorded_at) : '—'}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs">{j.job_id}</td>
                    <td className="px-4 py-2.5 max-w-[180px] truncate">{j.job_name || '—'}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">{j.owner_name || '—'}</td>
                    <td className="px-4 py-2.5 text-right font-medium">{j.printed_pages}</td>
                    <td className="px-4 py-2.5 text-right text-blue-600">{j.color_pages || '—'}</td>
                    <td className="px-4 py-2.5 text-right text-muted-foreground">{j.bw_pages || '—'}</td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground">{j.paper_type || '—'}</td>
                    <td className="px-4 py-2.5">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        j.status === 'completed' ? 'bg-green-100 text-green-700' :
                        j.status === 'failed' ? 'bg-red-100 text-red-700' :
                        j.status === 'cancelled' ? 'bg-amber-100 text-amber-700' :
                        'bg-gray-100 text-gray-600'
                      }`}>
                        {j.status || 'unknown'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="border-t px-5 py-3 flex items-center justify-between">
            <Button
              variant="outline"
              size="sm"
              disabled={filters.page <= 1}
              onClick={() => set('page')(filters.page - 1)}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Prev
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {filters.page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={filters.page >= totalPages}
              onClick={() => set('page')(filters.page + 1)}
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
