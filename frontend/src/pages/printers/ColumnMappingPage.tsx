import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ArrowLeft, Save } from 'lucide-react';
import { ColumnMappingExportImport } from '@/components/printers/ColumnMappingExportImport';

interface FieldDef {
  key: string;
  label: string;
  description: string;
  required?: boolean;
}

interface FieldGroup {
  title: string;
  fields: FieldDef[];
}

const FIELD_GROUPS: FieldGroup[] = [
  {
    title: 'Job Identity',
    fields: [
      { key: 'job_id', label: 'Job ID', description: 'Unique identifier for the print job', required: true },
      { key: 'job_name', label: 'Job Name', description: 'Document or file name' },
      { key: 'status', label: 'Status', description: 'completed / failed / cancelled / error' },
      { key: 'owner_name', label: 'Owner / User', description: 'Who submitted the job' },
      { key: 'error_info', label: 'Error Info', description: 'Error message if job failed' },
    ],
  },
  {
    title: 'Timestamps',
    fields: [
      { key: 'recorded_at', label: 'Recorded At', description: 'Main date/time of the job (used for analytics)' },
      { key: 'arrived_at', label: 'Arrived At', description: 'When job arrived at the printer queue' },
      { key: 'printed_at', label: 'Printed At', description: 'When printing completed' },
    ],
  },
  {
    title: 'Paper & Media',
    fields: [
      { key: 'paper_type', label: 'Paper Type', description: 'Media/paper type name (must match cost config names exactly)' },
      { key: 'paper_size', label: 'Paper Size', description: 'e.g. A4, Letter, A3' },
      { key: 'paper_width_mm', label: 'Paper Width (mm)', description: 'Custom paper width in millimetres' },
      { key: 'paper_length_mm', label: 'Paper Length (mm)', description: 'Custom paper length in millimetres' },
      { key: 'color_mode', label: 'Color Mode', description: 'e.g. color, grayscale, black' },
      { key: 'is_duplex', label: 'Duplex', description: 'true/false — double-sided printing' },
    ],
  },
  {
    title: 'Page Counts',
    fields: [
      { key: 'copies', label: 'Copies', description: 'Number of copies printed' },
      { key: 'input_pages', label: 'Input Pages', description: 'Pages in the source document' },
      { key: 'printed_pages', label: 'Printed Pages', description: 'Total pages actually printed' },
      { key: 'color_pages', label: 'Color Pages', description: 'Number of color pages' },
      { key: 'bw_pages', label: 'B&W Pages', description: 'Number of black & white pages' },
      { key: 'printed_sheets', label: 'Printed Sheets', description: 'Physical sheets used' },
      { key: 'waste_sheets', label: 'Waste Sheets', description: 'Sheets wasted (jams, reruns)' },
      { key: 'blank_pages', label: 'Blank Pages', description: 'Empty/blank pages' },
    ],
  },
  {
    title: 'Specialty Pages',
    fields: [
      { key: 'specialty_pages', label: 'Specialty Pages', description: 'Total specialty media pages' },
      { key: 'gold_pages', label: 'Gold Pages', description: 'Gold foil / gold toner pages' },
      { key: 'silver_pages', label: 'Silver Pages', description: 'Silver foil / silver toner pages' },
      { key: 'clear_pages', label: 'Clear Pages', description: 'Clear/varnish toner pages' },
      { key: 'white_pages', label: 'White Pages', description: 'White toner pages' },
      { key: 'texture_pages', label: 'Texture Pages', description: 'Texture toner pages' },
      { key: 'pink_pages', label: 'Pink Pages', description: 'Pink toner pages' },
    ],
  },
];

export default function ColumnMappingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const { data: printer } = useQuery({
    queryKey: ['printer', id],
    queryFn: () => api.get(`/printers/${id}`).then(r => r.data.data),
  });

  useEffect(() => {
    if (printer?.column_mapping) {
      setMapping(printer.column_mapping);
    }
  }, [printer]);

  const setField = (key: string, val: string) => {
    setMapping((m) => {
      const next = { ...m };
      if (val.trim()) next[key] = val.trim();
      else delete next[key];
      return next;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/printers/${id}`, { column_mapping: mapping });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setSaving(false);
    }
  };

  const handleClear = () => setMapping({});

  return (
    <div className="max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(`/printers/${id}`)} className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">Column Mapping</h1>
          <p className="text-sm text-muted-foreground">
            {printer?.name} — map your CSV column headers to PrintSight fields
          </p>
        </div>
        {id && (
          <ColumnMappingExportImport
            printerId={id}
            onApplied={() => {
              qc.invalidateQueries({ queryKey: ['printer', id] });
            }}
          />
        )}
      </div>

      {/* Instructions */}
      <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 text-sm text-blue-800">
        <p className="font-medium mb-1">How it works</p>
        <p>In the <strong>"Your CSV Column"</strong> box, enter the exact column header that appears in your CSV file. Leave blank if your CSV already uses the field name shown on the left.</p>
        <p className="mt-1 text-xs text-blue-600">Example: if your CSV has a column called <code className="bg-blue-100 px-1 rounded">PrintDate</code>, enter <code className="bg-blue-100 px-1 rounded">PrintDate</code> in the "Recorded At" row.</p>
      </div>

      {/* Table header legend */}
      <div className="grid grid-cols-[1fr_140px_1fr] gap-3 px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider border-b">
        <span>PrintSight Field</span>
        <span className="text-center">Field Key</span>
        <span>Your CSV Column (leave blank if same)</span>
      </div>

      {/* Field groups */}
      <div className="space-y-6">
        {FIELD_GROUPS.map((group) => (
          <div key={group.title} className="rounded-lg border bg-card overflow-hidden">
            <div className="px-4 py-2.5 bg-muted/50 border-b">
              <h3 className="font-semibold text-sm">{group.title}</h3>
            </div>
            <div className="divide-y">
              {group.fields.map((field) => (
                <div key={field.key} className="grid grid-cols-[1fr_140px_1fr] gap-3 items-center px-4 py-3">
                  {/* Label */}
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-medium">{field.label}</span>
                      {field.required && (
                        <span className="text-xs text-destructive font-medium">required</span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{field.description}</p>
                  </div>

                  {/* Field key pill */}
                  <div className="flex justify-center">
                    <code className="rounded bg-muted px-2 py-1 text-xs font-mono text-muted-foreground">
                      {field.key}
                    </code>
                  </div>

                  {/* CSV column input */}
                  <div>
                    <Input
                      placeholder={`e.g. ${field.key}`}
                      value={mapping[field.key] ?? ''}
                      onChange={(e) => setField(field.key, e.target.value)}
                      className={mapping[field.key] ? 'border-primary/50 bg-primary/5' : ''}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Mapped summary */}
      {Object.keys(mapping).length > 0 && (
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm font-medium mb-2">
            Active mappings ({Object.keys(mapping).length}):
          </p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(mapping).map(([field, col]) => (
              <span key={field} className="rounded-full bg-primary/10 text-primary px-3 py-1 text-xs font-medium">
                <span className="font-mono">{col}</span> → {field}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 pb-8">
        <Button variant="outline" onClick={() => navigate(`/printers/${id}`)}>Cancel</Button>
        {Object.keys(mapping).length > 0 && (
          <Button variant="outline" onClick={handleClear} className="text-destructive hover:text-destructive">
            Clear All
          </Button>
        )}
        <Button onClick={handleSave} isLoading={saving}>
          <Save className="mr-2 h-4 w-4" />
          {saved ? 'Saved!' : 'Save Mapping'}
        </Button>
      </div>
    </div>
  );
}
