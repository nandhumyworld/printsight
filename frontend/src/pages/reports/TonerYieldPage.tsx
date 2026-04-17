import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { formatDate } from '@/lib/utils';
import { Tally5, TrendingUp, TrendingDown, Minus, ChevronDown, ChevronRight } from 'lucide-react';

interface TonerEntry {
  toner_id: number;
  toner_color: string;
  toner_type: string;
  rated_yield_pages: number | null;
  price_per_unit: number | null;
  printer_name: string;
  printer_id: number;
  avg_efficiency_pct: number | null;
  avg_actual_yield: number | null;
  total_replacements: number;
  last_replaced_at: string | null;
  replacements: Replacement[];
}

interface Replacement {
  id: number;
  replaced_at: string;
  counter_reading: number;
  actual_yield_pages: number;
  yield_efficiency_pct: number | null;
  notes: string | null;
}

function EfficiencyBadge({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-muted-foreground text-xs">—</span>;
  const color = pct >= 90 ? 'text-green-600 bg-green-50' : pct >= 70 ? 'text-yellow-600 bg-yellow-50' : 'text-red-600 bg-red-50';
  const Icon = pct >= 90 ? TrendingUp : pct >= 70 ? Minus : TrendingDown;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      <Icon className="h-3 w-3" />
      {pct.toFixed(1)}%
    </span>
  );
}

function ColorDot({ color }: { color: string }) {
  const map: Record<string, string> = {
    black: 'bg-gray-900',
    cyan: 'bg-cyan-500',
    magenta: 'bg-pink-500',
    yellow: 'bg-yellow-400',
  };
  const key = color.toLowerCase().split(' ')[0];
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${map[key] ?? 'bg-primary'}`} />;
}

function TonerRow({ toner }: { toner: TonerEntry }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        className="hover:bg-muted/30 cursor-pointer"
        onClick={() => toner.replacements.length > 0 && setExpanded(e => !e)}
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {toner.replacements.length > 0 ? (
              expanded ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
            ) : (
              <span className="w-3.5" />
            )}
            <ColorDot color={toner.toner_color} />
            <span className="font-medium">{toner.toner_color}</span>
            <span className="text-xs text-muted-foreground capitalize">({toner.toner_type})</span>
          </div>
        </td>
        <td className="px-4 py-3 text-muted-foreground text-sm">{toner.printer_name}</td>
        <td className="px-4 py-3 text-right text-sm">
          {toner.rated_yield_pages != null ? toner.rated_yield_pages.toLocaleString() : '—'}
        </td>
        <td className="px-4 py-3 text-right text-sm">
          {toner.avg_actual_yield != null ? toner.avg_actual_yield.toLocaleString() : '—'}
        </td>
        <td className="px-4 py-3 text-right">
          <EfficiencyBadge pct={toner.avg_efficiency_pct} />
        </td>
        <td className="px-4 py-3 text-right text-sm text-muted-foreground">{toner.total_replacements}</td>
        <td className="px-4 py-3 text-right text-sm text-muted-foreground">
          {toner.last_replaced_at ? formatDate(toner.last_replaced_at) : '—'}
        </td>
        <td className="px-4 py-3 text-right text-sm">
          {toner.price_per_unit != null && toner.avg_actual_yield
            ? `₹${(toner.price_per_unit / toner.avg_actual_yield).toFixed(3)}`
            : '—'}
        </td>
      </tr>
      {expanded && toner.replacements.map(r => (
        <tr key={r.id} className="bg-muted/20 text-sm">
          <td className="pl-12 pr-4 py-2 text-muted-foreground">{formatDate(r.replaced_at)}</td>
          <td className="px-4 py-2 text-muted-foreground text-xs">Counter: {r.counter_reading.toLocaleString()}</td>
          <td className="px-4 py-2 text-right text-muted-foreground">—</td>
          <td className="px-4 py-2 text-right">{r.actual_yield_pages.toLocaleString()}</td>
          <td className="px-4 py-2 text-right">
            <EfficiencyBadge pct={r.yield_efficiency_pct} />
          </td>
          <td className="px-4 py-2 text-right text-muted-foreground">—</td>
          <td className="px-4 py-2 text-right text-muted-foreground text-xs">{r.notes || '—'}</td>
          <td className="px-4 py-2 text-right">—</td>
        </tr>
      ))}
    </>
  );
}

export default function TonerYieldPage() {
  const [filterPrinter, setFilterPrinter] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['toner-yield-summary'],
    queryFn: () => api.get('/toner-replacements/yield-summary').then(r => r.data.data as TonerEntry[]),
  });

  const printerNames = [...new Set((data ?? []).map(t => t.printer_name))];

  const filtered = (data ?? []).filter(t =>
    !filterPrinter || t.printer_name === filterPrinter
  );

  // Summary stats
  const withData = (data ?? []).filter(t => t.avg_efficiency_pct != null);
  const overallAvg = withData.length
    ? withData.reduce((s, t) => s + (t.avg_efficiency_pct ?? 0), 0) / withData.length
    : null;
  const highPerformers = withData.filter(t => (t.avg_efficiency_pct ?? 0) >= 90).length;
  const underperformers = withData.filter(t => (t.avg_efficiency_pct ?? 0) < 70).length;
  const totalReplacements = (data ?? []).reduce((s, t) => s + t.total_replacements, 0);

  return (
    <div className="max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Tally5 className="h-6 w-6 text-primary" />
          Toner Yield Report
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Track cartridge efficiency and cost per page across all printers
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">Overall Avg Efficiency</p>
          <p className={`text-2xl font-bold mt-1 ${overallAvg == null ? 'text-muted-foreground' : overallAvg >= 90 ? 'text-green-600' : overallAvg >= 70 ? 'text-yellow-600' : 'text-red-600'}`}>
            {overallAvg != null ? `${overallAvg.toFixed(1)}%` : '—'}
          </p>
          <p className="text-xs text-muted-foreground mt-1">vs rated yield</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">Total Replacements</p>
          <p className="text-2xl font-bold mt-1">{totalReplacements}</p>
          <p className="text-xs text-muted-foreground mt-1">logged events</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">High Performers</p>
          <p className="text-2xl font-bold mt-1 text-green-600">{highPerformers}</p>
          <p className="text-xs text-muted-foreground mt-1">≥ 90% efficiency</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">Underperforming</p>
          <p className="text-2xl font-bold mt-1 text-red-600">{underperformers}</p>
          <p className="text-xs text-muted-foreground mt-1">&lt; 70% efficiency</p>
        </div>
      </div>

      {/* Filter */}
      {printerNames.length > 1 && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">Filter by printer:</span>
          <select
            className="rounded-md border border-border bg-background px-3 py-1.5 text-sm"
            value={filterPrinter}
            onChange={e => setFilterPrinter(e.target.value)}
          >
            <option value="">All printers</option>
            {printerNames.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      )}

      {/* Table */}
      <div className="rounded-lg border bg-card overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">Loading yield data...</div>
        ) : !filtered.length ? (
          <div className="p-12 text-center text-muted-foreground">
            <Tally5 className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No yield data yet</p>
            <p className="text-sm mt-1">
              Log toner replacements in{' '}
              <a href="/settings/toner-replacements" className="text-primary hover:underline">
                Settings → Toner Replacements
              </a>{' '}
              to see efficiency trends here.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">Toner</th>
                <th className="px-4 py-3 text-left">Printer</th>
                <th className="px-4 py-3 text-right">Rated Yield</th>
                <th className="px-4 py-3 text-right">Avg Actual Yield</th>
                <th className="px-4 py-3 text-right">Avg Efficiency</th>
                <th className="px-4 py-3 text-right">Replacements</th>
                <th className="px-4 py-3 text-right">Last Replaced</th>
                <th className="px-4 py-3 text-right">Cost/Page</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filtered.map(t => <TonerRow key={t.toner_id} toner={t} />)}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-xs text-muted-foreground">
        Click any row to expand individual replacement history. Efficiency = actual pages / rated yield × 100.
        Cost per page = cartridge price ÷ average actual yield.
      </p>
    </div>
  );
}
