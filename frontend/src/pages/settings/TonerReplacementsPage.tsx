import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { formatDate } from '@/lib/utils';
import { Plus, Trash2 } from 'lucide-react';

function AddReplacementForm({ printers, onDone }: { printers: any[]; onDone: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    printer_id: '',
    toner_id: '',
    counter_reading_at_replacement: '',
    replaced_at: new Date().toISOString().slice(0, 16),
    cartridge_price_per_unit: '',
    cartridge_rated_yield_pages: '',
    cartridge_currency: 'INR',
    notes: '',
  });

  const set = (f: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm(p => ({ ...p, [f]: e.target.value }));

  const { data: toners } = useQuery({
    queryKey: ['toners', form.printer_id],
    queryFn: () => api.get(`/printers/${form.printer_id}/toners`).then(r => r.data.data),
    enabled: !!form.printer_id,
  });

  const handleTonerSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const tonerId = e.target.value;
    const selected = toners?.find((t: any) => String(t.id) === tonerId);
    setForm(p => ({
      ...p,
      toner_id: tonerId,
      cartridge_price_per_unit: selected ? String(selected.price_per_unit) : '',
      cartridge_rated_yield_pages: selected ? String(selected.rated_yield_pages) : '',
      cartridge_currency: selected?.currency ?? 'INR',
    }));
  };

  const create = useMutation({
    mutationFn: () => api.post('/toner-replacements', {
      printer_id: parseInt(form.printer_id),
      toner_id: parseInt(form.toner_id),
      counter_reading_at_replacement: parseInt(form.counter_reading_at_replacement),
      replaced_at: new Date(form.replaced_at).toISOString(),
      cartridge_price_per_unit: parseFloat(form.cartridge_price_per_unit),
      cartridge_rated_yield_pages: parseInt(form.cartridge_rated_yield_pages),
      cartridge_currency: form.cartridge_currency,
      notes: form.notes || undefined,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['replacements'] }); onDone(); },
  });

  return (
    <div className="rounded-md border bg-muted/30 p-4 space-y-3">
      <h3 className="font-medium text-sm">Log Toner Replacement</h3>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label>Printer *</Label>
          <select
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={form.printer_id}
            onChange={(e) => setForm(p => ({ ...p, printer_id: e.target.value, toner_id: '' }))}
          >
            <option value="">Select printer...</option>
            {printers.map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <Label>Toner *</Label>
          <select
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={form.toner_id}
            onChange={handleTonerSelect}
            disabled={!form.printer_id}
          >
            <option value="">Select toner...</option>
            {toners?.map((t: any) => <option key={t.id} value={t.id}>{t.toner_color} ({t.toner_type})</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <Label>Counter Reading *</Label>
          <Input type="number" placeholder="e.g. 45230" value={form.counter_reading_at_replacement} onChange={set('counter_reading_at_replacement')} />
        </div>
        <div className="space-y-1">
          <Label>Date & Time *</Label>
          <Input type="datetime-local" value={form.replaced_at} onChange={set('replaced_at')} />
        </div>
        <div className="space-y-1">
          <Label>Cartridge Price (pre-filled, editable) *</Label>
          <div className="flex gap-2">
            <Input
              type="number" min="0" step="0.01"
              placeholder="e.g. 5000"
              value={form.cartridge_price_per_unit}
              onChange={set('cartridge_price_per_unit')}
            />
            <select
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={form.cartridge_currency}
              onChange={set('cartridge_currency')}
            >
              <option value="INR">INR</option>
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
            </select>
          </div>
        </div>
        <div className="space-y-1">
          <Label>Cartridge Rated Yield (pages, pre-filled, editable) *</Label>
          <Input
            type="number" min="1"
            placeholder="e.g. 10000"
            value={form.cartridge_rated_yield_pages}
            onChange={set('cartridge_rated_yield_pages')}
          />
        </div>
        <div className="col-span-2 space-y-1">
          <Label>Notes</Label>
          <Input placeholder="Optional notes..." value={form.notes} onChange={set('notes')} />
        </div>
      </div>
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() => create.mutate()}
          isLoading={create.isPending}
          disabled={!form.printer_id || !form.toner_id || !form.counter_reading_at_replacement || !form.cartridge_price_per_unit || !form.cartridge_rated_yield_pages}
        >
          Log Replacement
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
      {create.isError && (
        <p className="text-sm text-destructive">{(create.error as any)?.response?.data?.detail || 'Failed to log replacement'}</p>
      )}
    </div>
  );
}

export default function TonerReplacementsPage() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);

  const { data: replacements, isLoading } = useQuery({
    queryKey: ['replacements'],
    queryFn: () => api.get('/toner-replacements').then(r => r.data.data),
  });

  const { data: printers } = useQuery({
    queryKey: ['printers'],
    queryFn: () => api.get('/printers').then(r => r.data.data),
  });

  const del = useMutation({
    mutationFn: (id: number) => api.delete(`/toner-replacements/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['replacements'] }),
  });

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Toner Replacements</h1>
          <p className="text-sm text-muted-foreground mt-1">Track toner cartridge changes and yield efficiency</p>
        </div>
        <Button onClick={() => setShowAdd(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Log Replacement
        </Button>
      </div>

      {showAdd && printers && (
        <AddReplacementForm printers={printers} onDone={() => setShowAdd(false)} />
      )}

      <div className="rounded-lg border bg-card overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">Loading...</div>
        ) : !replacements || replacements.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground">
            <p>No toner replacements logged yet.</p>
            <button onClick={() => setShowAdd(true)} className="mt-2 text-sm text-primary hover:underline">
              Log the first replacement →
            </button>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">Date</th>
                <th className="px-4 py-3 text-left">Printer</th>
                <th className="px-4 py-3 text-left">Toner</th>
                <th className="px-4 py-3 text-right">Counter</th>
                <th className="px-4 py-3 text-right">Cart. Price</th>
                <th className="px-4 py-3 text-right">Actual Yield</th>
                <th className="px-4 py-3 text-right">Efficiency</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {replacements.map((r: any) => (
                <tr key={r.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3">{formatDate(r.replaced_at)}</td>
                  <td className="px-4 py-3">
                    {printers?.find((p: any) => p.id === r.printer_id)?.name ?? `Printer #${r.printer_id}`}
                  </td>
                  <td className="px-4 py-3">
                    {r.toner_color ? `${r.toner_color}${r.toner_type ? ` (${r.toner_type})` : ''}` : `Toner #${r.toner_id}`}
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">{r.counter_reading_at_replacement.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {r.cartridge_price_per_unit != null ? `${r.cartridge_currency ?? 'INR'} ${parseFloat(r.cartridge_price_per_unit).toLocaleString()}` : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {r.actual_yield_pages != null ? r.actual_yield_pages.toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {r.yield_efficiency_pct != null ? (
                      <span className={`font-medium ${r.yield_efficiency_pct >= 90 ? 'text-green-600' : r.yield_efficiency_pct >= 70 ? 'text-yellow-600' : 'text-red-600'}`}>
                        {parseFloat(r.yield_efficiency_pct).toFixed(1)}%
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => del.mutate(r.id)} className="text-muted-foreground hover:text-destructive p-1">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
