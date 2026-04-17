import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Plus, Trash2, Edit, X, Check } from 'lucide-react';
import type { Paper } from '@/types';

function PaperRow({ paper, onDelete }: { paper: Paper; onDelete: (id: number) => void }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [price, setPrice] = useState(String(paper.price_per_sheet));

  const update = useMutation({
    mutationFn: () => api.put(`/cost-config/papers/${paper.id}`, { price_per_sheet: parseFloat(price) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['papers'] }); setEditing(false); },
  });

  return (
    <tr className="hover:bg-muted/30">
      <td className="px-4 py-3 font-medium">{paper.name}</td>
      <td className="px-4 py-3 text-muted-foreground">{paper.display_name || '-'}</td>
      <td className="px-4 py-3">
        {editing ? (
          <Input
            type="number"
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className="h-7 w-28"
          />
        ) : (
          <span>{paper.currency} {parseFloat(String(paper.price_per_sheet)).toFixed(4)}</span>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        <div className="flex items-center justify-end gap-1">
          {editing ? (
            <>
              <button onClick={() => update.mutate()} className="text-green-600 hover:text-green-800 p-1">
                <Check className="h-4 w-4" />
              </button>
              <button onClick={() => setEditing(false)} className="text-muted-foreground hover:text-foreground p-1">
                <X className="h-4 w-4" />
              </button>
            </>
          ) : (
            <>
              <button onClick={() => setEditing(true)} className="text-muted-foreground hover:text-primary p-1">
                <Edit className="h-4 w-4" />
              </button>
              <button onClick={() => onDelete(paper.id)} className="text-muted-foreground hover:text-destructive p-1">
                <Trash2 className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
      </td>
    </tr>
  );
}

function AddPaperForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ name: '', display_name: '', price_per_sheet: '', currency: 'INR' });
  const set = (f: string) => (e: React.ChangeEvent<HTMLInputElement>) => setForm(p => ({ ...p, [f]: e.target.value }));

  const create = useMutation({
    mutationFn: () => api.post('/cost-config/papers', {
      name: form.name,
      display_name: form.display_name || undefined,
      price_per_sheet: parseFloat(form.price_per_sheet),
      currency: form.currency,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['papers'] }); onDone(); },
  });

  return (
    <div className="rounded-md border bg-muted/30 p-4 space-y-3">
      <h3 className="font-medium text-sm">Add Paper Type</h3>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label>CSV Name (exact match) *</Label>
          <Input placeholder="e.g. A4 Plain" value={form.name} onChange={set('name')} />
        </div>
        <div className="space-y-1">
          <Label>Display Name</Label>
          <Input placeholder="e.g. A4 80gsm" value={form.display_name} onChange={set('display_name')} />
        </div>
        <div className="space-y-1">
          <Label>Price per Sheet *</Label>
          <Input type="number" step="0.0001" placeholder="0.50" value={form.price_per_sheet} onChange={set('price_per_sheet')} />
        </div>
        <div className="space-y-1">
          <Label>Currency</Label>
          <Input placeholder="INR" value={form.currency} onChange={set('currency')} />
        </div>
      </div>
      <div className="flex gap-2">
        <Button size="sm" onClick={() => create.mutate()} isLoading={create.isPending} disabled={!form.name || !form.price_per_sheet}>
          Add Paper
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </div>
  );
}

export default function CostConfigPage() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);

  const { data: papers, isLoading } = useQuery({
    queryKey: ['papers'],
    queryFn: () => api.get('/cost-config/papers').then(r => r.data.data as Paper[]),
  });

  const deletePaper = useMutation({
    mutationFn: (id: number) => api.delete(`/cost-config/papers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['papers'] }),
  });

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Paper & Cost Configuration</h1>
        <p className="text-sm text-muted-foreground mt-1">Configure paper types and pricing for cost calculations</p>
      </div>

      <div className="rounded-lg border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b flex items-center justify-between">
          <h2 className="font-semibold">Paper Types</h2>
          <Button size="sm" onClick={() => setShowAdd(true)}>
            <Plus className="mr-1.5 h-4 w-4" />
            Add Paper
          </Button>
        </div>

        {showAdd && (
          <div className="p-4 border-b">
            <AddPaperForm onDone={() => setShowAdd(false)} />
          </div>
        )}

        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground text-sm">Loading...</div>
        ) : !papers || papers.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground text-sm">
            No paper types configured yet. Add one to enable cost calculations.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">CSV Name</th>
                <th className="px-4 py-3 text-left">Display Name</th>
                <th className="px-4 py-3 text-left">Price/Sheet</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {papers.map((p) => (
                <PaperRow key={p.id} paper={p} onDelete={(id) => deletePaper.mutate(id)} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
