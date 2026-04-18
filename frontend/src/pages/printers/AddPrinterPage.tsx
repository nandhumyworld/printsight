import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Check, ChevronRight } from 'lucide-react';
import { usePrinter } from '@/context/PrinterContext';

const STEPS = [
  { label: 'Basic Info',    desc: 'Name, model, location' },
  { label: 'Toners',        desc: 'At least one toner required' },
  { label: 'Paper Types',   desc: 'Link paper configurations' },
  { label: 'Column Map',    desc: 'CSV field mapping' },
  { label: 'Review',        desc: 'Confirm and create' },
];

interface TonerDraft {
  toner_color: string;
  toner_type: string;
  price_per_unit: string;
  rated_yield_pages: string;
  currency: string;
}

export default function AddPrinterPage() {
  const navigate = useNavigate();
  const { refetchPrinters } = usePrinter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [info, setInfo] = useState({ name: '', model: '', type: '', serial_number: '', location: '' });

  const [toners, setToners] = useState<TonerDraft[]>([
    { toner_color: 'Black', toner_type: 'standard', price_per_unit: '', rated_yield_pages: '', currency: 'INR' },
  ]);

  const setInfo$ = (f: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setInfo(p => ({ ...p, [f]: e.target.value }));

  const updateToner = (i: number, f: string, v: string) =>
    setToners(ts => ts.map((t, idx) => idx === i ? { ...t, [f]: v } : t));

  const addToner = () =>
    setToners(ts => [...ts, { toner_color: '', toner_type: 'standard', price_per_unit: '', rated_yield_pages: '', currency: 'INR' }]);

  const removeToner = (i: number) => setToners(ts => ts.filter((_, idx) => idx !== i));

  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [mappingKey, setMappingKey] = useState('');
  const [mappingVal, setMappingVal] = useState('');

  const addMapping = () => {
    if (!mappingKey.trim() || !mappingVal.trim()) return;
    setMapping(m => ({ ...m, [mappingKey.trim()]: mappingVal.trim() }));
    setMappingKey('');
    setMappingVal('');
  };

  const removeMapping = (k: string) => setMapping(m => { const n = { ...m }; delete n[k]; return n; });

  const canNext = () => {
    if (step === 0) return info.name.trim().length > 0;
    if (step === 1) return toners.length > 0 && toners.every(t => t.toner_color && t.price_per_unit && t.rated_yield_pages);
    return true;
  };

  const handleCreate = async () => {
    setError('');
    setLoading(true);
    try {
      const { data: p } = await api.post('/printers', {
        name: info.name,
        model: info.model || undefined,
        type: info.type || undefined,
        serial_number: info.serial_number || undefined,
        location: info.location || undefined,
        column_mapping: mapping,
      });
      const pid = p.data.id;

      await Promise.all(
        toners.map(t =>
          api.post(`/printers/${pid}/toners`, {
            toner_color: t.toner_color,
            toner_type: t.toner_type,
            price_per_unit: parseFloat(t.price_per_unit),
            rated_yield_pages: parseInt(t.rated_yield_pages),
            currency: t.currency,
          })
        )
      );

      await refetchPrinters();
      navigate(`/printers/${pid}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create printer');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      {/* Progress bar */}
      <div>
        <div className="flex items-center gap-1 mb-4">
          {STEPS.map((s, i) => (
            <div key={i} className="flex items-center gap-1">
              <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium transition-colors ${i < step ? 'bg-primary text-primary-foreground' : i === step ? 'bg-primary/20 text-primary border border-primary' : 'bg-muted text-muted-foreground'}`}>
                {i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </div>
              {i < STEPS.length - 1 && <div className={`h-px w-6 ${i < step ? 'bg-primary' : 'bg-border'}`} />}
            </div>
          ))}
        </div>
        <h1 className="text-2xl font-bold">{STEPS[step].label}</h1>
        <p className="text-sm text-muted-foreground">{STEPS[step].desc}</p>
      </div>

      <div className="rounded-lg border bg-card p-6 space-y-4">

        {/* Step 0: Basic Info */}
        {step === 0 && (
          <>
            <div className="space-y-1">
              <Label>Printer Name *</Label>
              <Input placeholder="e.g. HP LaserJet 1st Floor" value={info.name} onChange={setInfo$('name')} required />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label>Model</Label>
                <Input placeholder="HP LaserJet Pro M404n" value={info.model} onChange={setInfo$('model')} />
              </div>
              <div className="space-y-1">
                <Label>Type</Label>
                <Input placeholder="Laser / Inkjet" value={info.type} onChange={setInfo$('type')} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label>Serial Number</Label>
                <Input placeholder="SN-XXXXX" value={info.serial_number} onChange={setInfo$('serial_number')} />
              </div>
              <div className="space-y-1">
                <Label>Location</Label>
                <Input placeholder="Office 2B" value={info.location} onChange={setInfo$('location')} />
              </div>
            </div>
          </>
        )}

        {/* Step 1: Toners */}
        {step === 1 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Add at least one toner. These become defaults for replacement logs.</p>
            {toners.map((t, i) => (
              <div key={i} className="rounded-md border p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Toner {i + 1}</span>
                  {toners.length > 1 && (
                    <button onClick={() => removeToner(i)} className="text-xs text-muted-foreground hover:text-destructive">Remove</button>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label>Color *</Label>
                    <Input placeholder="Black / Cyan / Gold…" value={t.toner_color} onChange={e => updateToner(i, 'toner_color', e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Type</Label>
                    <select className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={t.toner_type} onChange={e => updateToner(i, 'toner_type', e.target.value)}>
                      <option value="standard">Standard</option>
                      <option value="specialty">Specialty</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label>Price per Unit *</Label>
                    <Input type="number" min="0" step="0.01" placeholder="e.g. 2500" value={t.price_per_unit} onChange={e => updateToner(i, 'price_per_unit', e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Rated Yield (pages) *</Label>
                    <Input type="number" min="1" placeholder="e.g. 3000" value={t.rated_yield_pages} onChange={e => updateToner(i, 'rated_yield_pages', e.target.value)} />
                  </div>
                </div>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={addToner}>+ Add Another Toner</Button>
          </div>
        )}

        {/* Step 2: Paper Types */}
        {step === 2 && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Paper types can be linked after creation from <strong>Settings → Cost Config</strong>.
              You can skip this step.
            </p>
            <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
              Paper linking is available on the printer detail page after creation.
            </div>
          </div>
        )}

        {/* Step 3: Column Mapping */}
        {step === 3 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Map CSV column headers to PrintSight fields. You can also configure this later.</p>
            <div className="flex gap-2">
              <Input placeholder="CSV column name" value={mappingKey} onChange={e => setMappingKey(e.target.value)} />
              <Input placeholder="PrintSight field" value={mappingVal} onChange={e => setMappingVal(e.target.value)} />
              <Button variant="outline" size="sm" onClick={addMapping} disabled={!mappingKey || !mappingVal}>Add</Button>
            </div>
            {Object.entries(mapping).length > 0 && (
              <div className="space-y-1">
                {Object.entries(mapping).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between rounded-md border px-3 py-1.5 text-sm">
                    <span><span className="font-mono">{k}</span> → <span className="font-mono text-primary">{v}</span></span>
                    <button onClick={() => removeMapping(k)} className="text-muted-foreground hover:text-destructive text-xs">Remove</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 4: Review */}
        {step === 4 && (
          <div className="space-y-3 text-sm">
            <div className="rounded-md bg-muted/40 p-4 space-y-1">
              <p><span className="text-muted-foreground">Name:</span> <strong>{info.name}</strong></p>
              {info.model && <p><span className="text-muted-foreground">Model:</span> {info.model}</p>}
              {info.type && <p><span className="text-muted-foreground">Type:</span> {info.type}</p>}
              {info.location && <p><span className="text-muted-foreground">Location:</span> {info.location}</p>}
              <p><span className="text-muted-foreground">Toners:</span> {toners.map(t => t.toner_color).join(', ')}</p>
              <p><span className="text-muted-foreground">Mapping fields:</span> {Object.keys(mapping).length || 'none'}</p>
            </div>
            {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-destructive">{error}</p>}
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={() => step > 0 ? setStep(s => s - 1) : navigate('/printers')} disabled={loading}>
          {step === 0 ? 'Cancel' : '← Back'}
        </Button>
        {step < STEPS.length - 1 ? (
          <Button onClick={() => setStep(s => s + 1)} disabled={!canNext()}>
            Next <ChevronRight className="ml-1.5 h-4 w-4" />
          </Button>
        ) : (
          <Button onClick={handleCreate} isLoading={loading}>
            Create Printer
          </Button>
        )}
      </div>
    </div>
  );
}
