import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { formatDateTime } from '@/lib/utils';
import { ArrowLeft, Upload, CheckCircle, AlertCircle, FileText, Loader2, Eye, X, Trash2, Plus, Edit } from 'lucide-react';

type UploadStep = 'idle' | 'previewing' | 'preview_ready' | 'importing' | 'done';

interface PreviewData {
  detected_columns: string[];
  suggested_mapping: Record<string, string>;
  preview_rows: Record<string, string>[];
  total_rows: number;
}

interface ImportResult {
  batch_id: number;
  rows_total: number;
  rows_imported: number;
  rows_skipped: number;
  skipped_details: { row_number: number; reason: string }[];
  message: string;
}

// Maps column-mapping field keys → toner color name + type
const FIELD_TO_TONER: Record<string, { color: string; type: 'standard' | 'specialty' }> = {
  bw_pages:       { color: 'Black',   type: 'standard' },
  color_pages:    { color: 'Cyan',    type: 'standard' },   // represents CMYK group
  gold_pages:     { color: 'Gold',    type: 'specialty' },
  silver_pages:   { color: 'Silver',  type: 'specialty' },
  clear_pages:    { color: 'Clear',   type: 'specialty' },
  white_pages:    { color: 'White',   type: 'specialty' },
  texture_pages:  { color: 'Texture', type: 'specialty' },
  pink_pages:     { color: 'Pink',    type: 'specialty' },
};

// Standard colors always shown
const STANDARD_COLORS = [
  { color: 'Black',   type: 'standard' as const },
  { color: 'Cyan',    type: 'standard' as const },
  { color: 'Magenta', type: 'standard' as const },
  { color: 'Yellow',  type: 'standard' as const },
];

function TonerManagement({ printerId, columnMapping }: {
  printerId: string;
  columnMapping: Record<string, string>;
}) {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ toner_color: '', toner_type: 'standard', price_per_unit: '', rated_yield_pages: '', currency: 'INR' });
  const [editToner, setEditToner] = useState<any | null>(null);
  const [editForm, setEditForm] = useState({ price_per_unit: '', rated_yield_pages: '', currency: 'INR' });

  const { data: toners, isLoading } = useQuery({
    queryKey: ['toners', printerId],
    queryFn: () => api.get(`/printers/${printerId}/toners`).then(r => r.data.data),
  });

  // Derive specialty toners from the printer's column mapping
  const mappedSpecialty = Object.keys(columnMapping)
    .filter(k => k in FIELD_TO_TONER && FIELD_TO_TONER[k].type === 'specialty')
    .map(k => FIELD_TO_TONER[k]);

  // All suggested colors = standard + mapped specialty (deduplicated)
  const suggestedColors = [
    ...STANDARD_COLORS,
    ...mappedSpecialty.filter(s => !STANDARD_COLORS.some(c => c.color === s.color)),
  ];

  // Which mapped specialty columns don't have a toner configured yet
  const existingColors = new Set((toners ?? []).map((t: any) => t.toner_color));
  const missingMapped = suggestedColors.filter(c => !existingColors.has(c.color));

  const addToner = useMutation({
    mutationFn: () => api.post(`/printers/${printerId}/toners`, {
      toner_color: form.toner_color,
      toner_type: form.toner_type,
      price_per_unit: parseFloat(form.price_per_unit),
      rated_yield_pages: parseInt(form.rated_yield_pages),
      currency: form.currency,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['toners', printerId] });
      setForm({ toner_color: '', toner_type: 'standard', price_per_unit: '', rated_yield_pages: '', currency: 'INR' });
      setShowAdd(false);
    },
  });

  const deleteToner = useMutation({
    mutationFn: (tonerId: number) => api.delete(`/printers/${printerId}/toners/${tonerId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['toners', printerId] }),
  });

  const updateToner = useMutation({
    mutationFn: () => api.put(`/printers/${printerId}/toners/${editToner.id}`, {
      toner_color: editToner.toner_color,
      toner_type: editToner.toner_type,
      price_per_unit: parseFloat(editForm.price_per_unit),
      rated_yield_pages: parseInt(editForm.rated_yield_pages),
      currency: editForm.currency,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['toners', printerId] });
      setEditToner(null);
    },
  });

  // When a color is picked from the dropdown, also auto-set the type
  const handleColorSelect = (color: string) => {
    const suggestion = suggestedColors.find(c => c.color === color);
    setForm(p => ({
      ...p,
      toner_color: color,
      toner_type: suggestion?.type ?? (STANDARD_COLORS.some(c => c.color === color) ? 'standard' : 'specialty'),
    }));
  };

  return (
    <div className="rounded-lg border bg-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold">Toner Cartridges</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Colors are derived from this printer's column mapping — standard + specialty page columns
          </p>
        </div>
        <Button size="sm" onClick={() => setShowAdd(true)}>
          <Plus className="mr-2 h-3.5 w-3.5" />
          Add Toner
        </Button>
      </div>

      {/* Alert: mapped specialty columns without a toner */}
      {!isLoading && toners && missingMapped.length > 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
          <span className="font-medium">Missing toner configs:</span>{' '}
          {missingMapped.map((c, i) => (
            <button
              key={c.color}
              onClick={() => { handleColorSelect(c.color); setShowAdd(true); }}
              className="underline hover:no-underline font-medium"
            >
              {c.color}{i < missingMapped.length - 1 ? ', ' : ''}
            </button>
          ))}{' '}
          — these page columns are mapped but have no toner cost configured.
        </div>
      )}

      {showAdd && (
        <div className="rounded-md border bg-muted/30 p-4 space-y-3">
          <h3 className="font-medium text-sm">Add Toner Cartridge</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1 col-span-2">
              <Label>Color *</Label>
              <div className="flex gap-2">
                <select
                  className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={form.toner_color}
                  onChange={e => handleColorSelect(e.target.value)}
                >
                  <option value="">Select color...</option>
                  <optgroup label="Standard">
                    {STANDARD_COLORS.map(c => (
                      <option key={c.color} value={c.color}>{c.color}</option>
                    ))}
                  </optgroup>
                  {mappedSpecialty.length > 0 && (
                    <optgroup label="Specialty (from column mapping)">
                      {mappedSpecialty.map(c => (
                        <option key={c.color} value={c.color}>{c.color}</option>
                      ))}
                    </optgroup>
                  )}
                  <optgroup label="Other">
                    <option value="__custom__">Custom color...</option>
                  </optgroup>
                </select>
                {(form.toner_color === '__custom__' || !suggestedColors.some(c => c.color === form.toner_color)) && (
                  <Input
                    className="w-36"
                    placeholder="e.g. Pink"
                    value={form.toner_color === '__custom__' ? '' : form.toner_color}
                    onChange={e => setForm(p => ({ ...p, toner_color: e.target.value }))}
                    autoFocus
                  />
                )}
              </div>
              {mappedSpecialty.length === 0 && (
                <p className="text-xs text-muted-foreground mt-1">
                  To see specialty toner options here, map specialty page columns (Gold, Silver, Clear, etc.) in{' '}
                  <a href={`/printers/${printerId}/mapping`} className="text-primary hover:underline">Column Mapping</a>.
                </p>
              )}
            </div>
            <div className="space-y-1">
              <Label>Type</Label>
              <select
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={form.toner_type}
                onChange={e => setForm(p => ({ ...p, toner_type: e.target.value }))}
              >
                <option value="standard">Standard</option>
                <option value="specialty">Specialty</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label>Currency</Label>
              <select
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={form.currency}
                onChange={e => setForm(p => ({ ...p, currency: e.target.value }))}
              >
                <option value="INR">INR</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label>Price per Unit *</Label>
              <Input type="number" min="0" step="0.01" placeholder="e.g. 2500" value={form.price_per_unit} onChange={e => setForm(p => ({ ...p, price_per_unit: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label>Rated Yield (pages) *</Label>
              <Input type="number" min="1" placeholder="e.g. 3000" value={form.rated_yield_pages} onChange={e => setForm(p => ({ ...p, rated_yield_pages: e.target.value }))} />
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => addToner.mutate()}
              disabled={!form.toner_color || form.toner_color === '__custom__' || !form.price_per_unit || !form.rated_yield_pages || addToner.isPending}
            >
              {addToner.isPending ? 'Adding...' : 'Add Toner'}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowAdd(false)}>Cancel</Button>
          </div>
          {addToner.isError && (
            <p className="text-sm text-destructive">{(addToner.error as any)?.response?.data?.detail || 'Failed to add toner'}</p>
          )}
        </div>
      )}

      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading toners...</div>
      ) : !toners || toners.length === 0 ? (
        <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          No toners configured yet.{' '}
          <button onClick={() => setShowAdd(true)} className="text-primary hover:underline">Add your first toner →</button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 text-left">Color</th>
                <th className="px-4 py-2.5 text-left">Type</th>
                <th className="px-4 py-2.5 text-right">Price</th>
                <th className="px-4 py-2.5 text-right">Rated Yield</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {toners.map((t: any) => (
                <tr key={t.id} className="hover:bg-muted/30">
                  <td className="px-4 py-2.5 font-medium">{t.toner_color}</td>
                  <td className="px-4 py-2.5 text-muted-foreground capitalize">{t.toner_type}</td>
                  <td className="px-4 py-2.5 text-right">{t.currency} {parseFloat(t.price_per_unit).toLocaleString()}</td>
                  <td className="px-4 py-2.5 text-right">{t.rated_yield_pages.toLocaleString()} pages</td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => {
                          setEditToner(t);
                          setEditForm({ price_per_unit: String(t.price_per_unit), rated_yield_pages: String(t.rated_yield_pages), currency: t.currency });
                        }}
                        className="text-muted-foreground hover:text-primary p-1"
                      >
                        <Edit className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => deleteToner.mutate(t.id)}
                        className="text-muted-foreground hover:text-destructive p-1"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Toner edit modal */}
      {editToner && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-xl border bg-card p-6 shadow-xl mx-4 space-y-4">
            <h3 className="font-semibold">Edit {editToner.toner_color} Toner</h3>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label>Price per Unit</Label>
                <Input type="number" min="0" step="0.01" value={editForm.price_per_unit} onChange={e => setEditForm(p => ({ ...p, price_per_unit: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <Label>Rated Yield (pages)</Label>
                <Input type="number" min="1" value={editForm.rated_yield_pages} onChange={e => setEditForm(p => ({ ...p, rated_yield_pages: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <Label>Currency</Label>
                <select className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={editForm.currency} onChange={e => setEditForm(p => ({ ...p, currency: e.target.value }))}>
                  <option value="INR">INR</option>
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                  <option value="GBP">GBP</option>
                </select>
              </div>
            </div>
            {updateToner.isError && <p className="text-sm text-destructive">{(updateToner.error as any)?.response?.data?.detail || 'Update failed'}</p>}
            <div className="flex gap-3">
              <Button variant="outline" size="sm" onClick={() => setEditToner(null)}>Cancel</Button>
              <Button size="sm" onClick={() => updateToner.mutate()} disabled={updateToner.isPending} isLoading={updateToner.isPending}>Save</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PrinterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const selectedFileRef = useRef<File | null>(null);

  const [confirmClear, setConfirmClear] = useState(false);
  const [step, setStep] = useState<UploadStep>('idle');
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [importResult, setImportResult] = useState<ImportResult & { success: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const clearJobs = useMutation({
    mutationFn: () => api.delete(`/printers/${id}/uploads/clear`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uploads', id] });
      qc.invalidateQueries({ queryKey: ['jobs', id] });
      qc.invalidateQueries({ queryKey: ['analytics-summary'] });
      qc.invalidateQueries({ queryKey: ['analytics-trends'] });
      setConfirmClear(false);
    },
  });

  const { data: printer, isLoading } = useQuery({
    queryKey: ['printer', id],
    queryFn: () => api.get(`/printers/${id}`).then(r => r.data.data),
  });

  const { data: uploads } = useQuery({
    queryKey: ['uploads', id],
    queryFn: () => api.get(`/printers/${id}/uploads`).then(r => r.data.data),
  });

  const { data: jobs } = useQuery({
    queryKey: ['jobs', id],
    queryFn: () => api.get(`/printers/${id}/jobs?per_page=50`).then(r => r.data),
  });

  const { data: toners } = useQuery({
    queryKey: ['toners', id],
    queryFn: () => api.get(`/printers/${id}/toners`).then(r => r.data.data),
  });

  const hasNoToners = Array.isArray(toners) && toners.length === 0;

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    selectedFileRef.current = file;
    setError(null);
    setImportResult(null);
    setStep('previewing');

    const form = new FormData();
    form.append('file', file);
    try {
      const { data } = await api.post(`/printers/${id}/uploads/preview`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPreview(data.data);
      setStep('preview_ready');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to read CSV');
      setStep('idle');
    }
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleConfirmImport = async () => {
    if (!selectedFileRef.current) return;
    setStep('importing');
    const form = new FormData();
    form.append('file', selectedFileRef.current);
    try {
      const { data } = await api.post(`/printers/${id}/uploads`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setImportResult({ success: true, ...data.data, message: data.message });
      qc.invalidateQueries({ queryKey: ['uploads', id] });
      qc.invalidateQueries({ queryKey: ['jobs', id] });
      qc.invalidateQueries({ queryKey: ['analytics-summary'] });
      qc.invalidateQueries({ queryKey: ['analytics-trends'] });
    } catch (err: any) {
      setImportResult({ success: false, message: err?.response?.data?.detail || 'Import failed' } as any);
    }
    setStep('done');
    setPreview(null);
    selectedFileRef.current = null;
  };

  const handleCancel = () => {
    setStep('idle');
    setPreview(null);
    setError(null);
    selectedFileRef.current = null;
    if (fileRef.current) fileRef.current.value = '';
  };

  if (isLoading) return <div className="h-40 animate-pulse rounded-lg bg-muted" />;
  if (!printer) return <div className="text-center py-20 text-muted-foreground">Printer not found</div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/printers')} className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{printer.name}</h1>
          <p className="text-sm text-muted-foreground">
            {[printer.model, printer.type, printer.location].filter(Boolean).join(' · ')}
          </p>
        </div>
        <button
          onClick={() => navigate(`/printers/${id}/edit`)}
          className="text-sm text-primary hover:underline"
        >
          Edit →
        </button>
      </div>

      {/* Upload Card */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Upload CSV Log</h2>
          <button
            onClick={() => navigate(`/printers/${id}/mapping`)}
            className="text-xs text-primary hover:underline"
          >
            Configure column mapping →
          </button>
        </div>

        {/* Upload gate: warn if no toners */}
        {hasNoToners && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <strong>CSV upload is disabled.</strong> Configure at least one toner cartridge below before uploading print logs.
          </div>
        )}

        {/* Step: idle or done */}
        {(step === 'idle' || step === 'done') && (
          <div
            className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 text-center cursor-pointer hover:border-primary hover:bg-muted/30 transition-colors"
            onClick={() => fileRef.current?.click()}
          >
            <Upload className="h-8 w-8 text-muted-foreground mb-2" />
            <p className="font-medium">Click to select a CSV file</p>
            <p className="text-xs text-muted-foreground mt-1">Max {10}MB · .csv only · Preview before importing</p>
          </div>
        )}

        {/* Step: previewing spinner */}
        {step === 'previewing' && (
          <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-10">
            <Loader2 className="h-8 w-8 animate-spin text-primary mb-2" />
            <p className="text-sm text-muted-foreground">Reading file columns...</p>
          </div>
        )}

        {/* Step: preview_ready */}
        {step === 'preview_ready' && preview && (
          <div className="space-y-4">
            <div className="rounded-lg bg-muted/40 border p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Eye className="h-4 w-4 text-primary" />
                  <span className="font-medium text-sm">
                    {selectedFileRef.current?.name} — {preview.total_rows.toLocaleString()} rows detected
                  </span>
                </div>
                <button onClick={handleCancel} className="text-muted-foreground hover:text-foreground">
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Suggested mapping */}
              {Object.keys(preview.suggested_mapping).length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1.5">Auto-detected field mapping:</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(preview.suggested_mapping).map(([field, col]) => (
                      <span key={field} className="rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs">
                        {field} ← <span className="font-mono">{col}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Detected columns */}
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1.5">
                  All detected columns ({preview.detected_columns.length}):
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {preview.detected_columns.map((col) => (
                    <span key={col} className="rounded bg-muted px-2 py-0.5 text-xs font-mono">{col}</span>
                  ))}
                </div>
              </div>
            </div>

            {/* 5-row preview table */}
            {preview.preview_rows.length > 0 && (
              <div className="overflow-x-auto rounded-lg border">
                <p className="px-3 py-2 text-xs text-muted-foreground bg-muted/40 border-b font-medium">
                  First {preview.preview_rows.length} rows preview:
                </p>
                <table className="w-full text-xs">
                  <thead className="bg-muted/50">
                    <tr>
                      {preview.detected_columns.map((col) => (
                        <th key={col} className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {preview.preview_rows.map((row, i) => (
                      <tr key={i} className="hover:bg-muted/30">
                        {preview.detected_columns.map((col) => (
                          <td key={col} className="px-3 py-1.5 whitespace-nowrap max-w-[160px] truncate">
                            {row[col] ?? ''}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="flex gap-3">
              <Button onClick={handleConfirmImport}>
                <Upload className="mr-2 h-4 w-4" />
                Confirm & Import {preview.total_rows.toLocaleString()} rows
              </Button>
              <Button variant="outline" onClick={handleCancel}>Cancel</Button>
            </div>
          </div>
        )}

        {/* Step: importing spinner */}
        {step === 'importing' && (
          <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-10">
            <Loader2 className="h-8 w-8 animate-spin text-primary mb-2" />
            <p className="text-sm text-muted-foreground">Importing rows...</p>
          </div>
        )}

        <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleFileSelected} />

        {/* Error */}
        {error && (
          <div className="rounded-lg p-3 bg-red-50 border border-red-200 flex items-center gap-2 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Import result */}
        {importResult && step === 'done' && (
          <div className={`rounded-lg p-4 ${importResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
            <div className="flex items-start gap-2">
              {importResult.success
                ? <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
                : <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />}
              <div className="flex-1">
                <p className={`font-medium text-sm ${importResult.success ? 'text-green-800' : 'text-red-800'}`}>
                  {importResult.message}
                </p>
                {importResult.success && (
                  <p className="text-xs mt-1 text-green-700">
                    {importResult.rows_imported} imported · {importResult.rows_skipped} skipped of {importResult.rows_total} total
                  </p>
                )}
                {importResult.skipped_details?.length > 0 && (
                  <div className="mt-2 max-h-28 overflow-y-auto space-y-0.5">
                    {importResult.skipped_details.slice(0, 10).map((s, i) => (
                      <p key={i} className="text-xs text-amber-700">Row {s.row_number}: {s.reason}</p>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Upload History */}
      {uploads && uploads.length > 0 && (
        <div className="rounded-lg border bg-card p-5">
          <h2 className="font-semibold mb-3">Upload History</h2>
          <div className="space-y-2">
            {uploads.map((u: any) => (
              <div key={u.id} className="flex items-center justify-between rounded-md border px-4 py-2.5 text-sm">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{u.filename}</span>
                </div>
                <div className="flex items-center gap-4 text-muted-foreground text-xs">
                  <span>{u.rows_imported}/{u.rows_total} rows</span>
                  <span>{formatDateTime(u.uploaded_at)}</span>
                  <span className={`rounded-full px-2 py-0.5 ${u.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {u.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Toner Management */}
      <TonerManagement printerId={id!} columnMapping={printer.column_mapping ?? {}} />

      {/* Jobs Table */}
      {jobs && jobs.data && jobs.data.length > 0 && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="px-5 py-4 border-b flex items-center justify-between">
            <h2 className="font-semibold">Recent Print Jobs</h2>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">{jobs.total} total</span>
              {!confirmClear ? (
                <button
                  onClick={() => setConfirmClear(true)}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-destructive transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Clear all jobs
                </button>
              ) : (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-destructive font-medium">Delete all jobs?</span>
                  <button
                    onClick={() => clearJobs.mutate()}
                    disabled={clearJobs.isPending}
                    className="rounded px-2 py-0.5 text-xs bg-destructive text-white hover:bg-destructive/90 disabled:opacity-50"
                  >
                    {clearJobs.isPending ? 'Clearing...' : 'Yes, clear'}
                  </button>
                  <button
                    onClick={() => setConfirmClear(false)}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 text-left">Job ID</th>
                  <th className="px-4 py-3 text-left">Name</th>
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-left">Owner</th>
                  <th className="px-4 py-3 text-right">Pages</th>
                  <th className="px-4 py-3 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {jobs.data.map((j: any) => (
                  <tr key={j.id} className="hover:bg-muted/30">
                    <td className="px-4 py-2.5 font-mono text-xs">{j.job_id}</td>
                    <td className="px-4 py-2.5 max-w-xs truncate">{j.job_name || '—'}</td>
                    <td className="px-4 py-2.5 text-muted-foreground text-xs">{j.recorded_at ? formatDateTime(j.recorded_at) : '—'}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">{j.owner_name || '—'}</td>
                    <td className="px-4 py-2.5 text-right">{j.printed_pages}</td>
                    <td className="px-4 py-2.5">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${j.is_waste ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                        {j.status || 'unknown'}
                      </span>
                    </td>
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
