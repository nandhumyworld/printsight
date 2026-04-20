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
      { key: 'sub_id', label: 'Sub ID', description: 'Sub-job identifier' },
      { key: 'jdf_job_id', label: 'JDF Job ID', description: 'JDF standard job ID' },
      { key: 'jdf_job_part_id', label: 'JDF Job Part ID', description: 'JDF part ID' },
      { key: 'job_name', label: 'Job Name', description: 'Document or file name' },
      { key: 'status', label: 'Status', description: 'completed / failed / cancelled / error' },
      { key: 'owner_name', label: 'Owner / User', description: 'Who submitted the job' },
      { key: 'logical_printer', label: 'Logical Printer', description: 'Printer queue name (e.g. lpr_hold)' },
      { key: 'template', label: 'Template', description: 'Print template used' },
      { key: 'imposition_settings', label: 'Imposition Settings', description: 'Imposition configuration' },
      { key: 'account', label: 'Account', description: 'Account or billing code' },
      { key: 'folder', label: 'Folder', description: 'Job folder path' },
      { key: 'tag', label: 'Tag', description: 'Job tag' },
      { key: 'comments', label: 'Comments', description: 'Free-text comments' },
      { key: 'banner_sheet', label: 'Banner Sheet', description: 'Banner sheet flag' },
      { key: 'change_output_destination', label: 'Change Output Destination', description: 'Output tray override' },
      { key: 'error_info', label: 'Error Info', description: 'Error message if job failed' },
    ],
  },
  {
    title: 'Timestamps',
    fields: [
      { key: 'recorded_at', label: 'Recorded At', description: 'Main date/time of the job (used for analytics)' },
      { key: 'arrived_at', label: 'Arrived At', description: 'When job arrived at the printer queue' },
      { key: 'printed_at', label: 'Printed At', description: 'When printing completed' },
      { key: 'conversion_start_at', label: 'Conversion Start', description: 'Conversion start date/time' },
      { key: 'conversion_elapsed', label: 'Conversion Elapsed', description: 'Elapsed conversion time (H:MM:SS)' },
      { key: 'rip_start_at', label: 'RIP Start', description: 'RIP start date/time' },
      { key: 'rip_elapsed', label: 'RIP Elapsed', description: 'RIP elapsed time (H:MM:SS)' },
      { key: 'rasterization_start_at', label: 'Rasterization Start', description: 'Rasterization start date/time' },
      { key: 'rasterization_elapsed', label: 'Rasterization Elapsed', description: 'Rasterization elapsed time (H:MM:SS)' },
      { key: 'printing_start_at', label: 'Printing Start', description: 'Printing start date/time' },
      { key: 'printing_elapsed', label: 'Printing Elapsed', description: 'Elapsed printing time (H:MM:SS)' },
    ],
  },
  {
    title: 'Paper & Media',
    fields: [
      { key: 'paper_type', label: 'Paper Type', description: 'Media/paper type name (must match cost config names exactly)' },
      { key: 'media_name', label: 'Media Name', description: 'Named media profile (e.g. 300 Art 12.5 x 18)' },
      { key: 'paper_tray', label: 'Paper Tray', description: 'Tray used (e.g. Tray 1, Bypass Tray)' },
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
      { key: 'print_collation', label: 'Collation', description: 'Collation setting (On/Off)' },
      { key: 'input_pages', label: 'Input Pages', description: 'Pages in the source document' },
      { key: 'printed_pages', label: 'Printed Pages', description: 'Total pages actually printed' },
      { key: 'color_pages', label: 'Color Pages', description: 'Number of color pages' },
      { key: 'bw_pages', label: 'B&W Pages', description: 'Number of black & white pages' },
      { key: 'printed_sheets', label: 'Printed Sheets', description: 'Physical sheets used' },
      { key: 'imposed_pages', label: 'Imposed Pages', description: 'Total imposed pages' },
      { key: 'last_printed_page', label: 'Last Printed Page', description: 'Last page printed (e.g. Copy 10, Page 2)' },
      { key: 'waste_sheets', label: 'Waste Sheets', description: 'Sheets wasted (jams, reruns)' },
      { key: 'blank_pages', label: 'Blank Pages', description: 'Empty/blank pages' },
    ],
  },
  {
    title: 'Specialty Pages — #1',
    fields: [
      { key: 'specialty_pages', label: 'Specialty Pages', description: 'Total specialty media pages' },
      { key: 'gold_pages', label: 'Gold (GLD #1)', description: 'Gold toner pages' },
      { key: 'silver_pages', label: 'Silver (SLV #1)', description: 'Silver toner pages' },
      { key: 'clear_pages', label: 'Clear (CLR #1)', description: 'Clear/varnish toner pages' },
      { key: 'white_pages', label: 'White (WHT #1)', description: 'White toner pages' },
      { key: 'texture_pages', label: 'Texture (CR #1)', description: 'Texture/crystal toner pages' },
      { key: 'pink_pages', label: 'Pink (P #1)', description: 'Pink toner pages' },
      { key: 'pa_pages', label: 'PA (PA #1)', description: 'PA toner pages' },
    ],
  },
  {
    title: 'Specialty Pages — #6',
    fields: [
      { key: 'gold_6_pages', label: 'Gold (GLD #6)', description: 'Gold #6 toner pages' },
      { key: 'silver_6_pages', label: 'Silver (SLV #6)', description: 'Silver #6 toner pages' },
      { key: 'white_6_pages', label: 'White (WHT #6)', description: 'White #6 toner pages' },
      { key: 'pink_6_pages', label: 'Pink (P #6)', description: 'Pink #6 toner pages' },
    ],
  },
  {
    title: 'Raster Coverage — CMYK',
    fields: [
      { key: 'coverage_k', label: 'Coverage K', description: 'Black raster coverage %' },
      { key: 'coverage_c', label: 'Coverage C', description: 'Cyan raster coverage %' },
      { key: 'coverage_m', label: 'Coverage M', description: 'Magenta raster coverage %' },
      { key: 'coverage_y', label: 'Coverage Y', description: 'Yellow raster coverage %' },
    ],
  },
  {
    title: 'Raster Coverage — Specialty #1',
    fields: [
      { key: 'coverage_gld_1', label: 'Coverage GLD #1', description: 'Gold #1 raster coverage %' },
      { key: 'coverage_slv_1', label: 'Coverage SLV #1', description: 'Silver #1 raster coverage %' },
      { key: 'coverage_clr_1', label: 'Coverage CLR #1', description: 'Clear #1 raster coverage %' },
      { key: 'coverage_wht_1', label: 'Coverage WHT #1', description: 'White #1 raster coverage %' },
      { key: 'coverage_cr_1', label: 'Coverage CR #1', description: 'Crystal #1 raster coverage %' },
      { key: 'coverage_p_1', label: 'Coverage P #1', description: 'Pink #1 raster coverage %' },
      { key: 'coverage_pa_1', label: 'Coverage PA #1', description: 'PA #1 raster coverage %' },
    ],
  },
  {
    title: 'Raster Coverage — Specialty #6',
    fields: [
      { key: 'coverage_gld_6', label: 'Coverage GLD #6', description: 'Gold #6 raster coverage %' },
      { key: 'coverage_slv_6', label: 'Coverage SLV #6', description: 'Silver #6 raster coverage %' },
      { key: 'coverage_wht_6', label: 'Coverage WHT #6', description: 'White #6 raster coverage %' },
      { key: 'coverage_p_6', label: 'Coverage P #6', description: 'Pink #6 raster coverage %' },
    ],
  },
  {
    title: 'Raster Coverage — Estimation CMYK',
    fields: [
      { key: 'coverage_est_k', label: 'Est. Coverage K', description: 'Estimated black raster coverage %' },
      { key: 'coverage_est_c', label: 'Est. Coverage C', description: 'Estimated cyan raster coverage %' },
      { key: 'coverage_est_m', label: 'Est. Coverage M', description: 'Estimated magenta raster coverage %' },
      { key: 'coverage_est_y', label: 'Est. Coverage Y', description: 'Estimated yellow raster coverage %' },
    ],
  },
  {
    title: 'Raster Coverage — Estimation Specialty',
    fields: [
      { key: 'coverage_est_gld_1', label: 'Est. Coverage GLD #1', description: 'Estimated gold #1 raster coverage %' },
      { key: 'coverage_est_slv_1', label: 'Est. Coverage SLV #1', description: 'Estimated silver #1 raster coverage %' },
      { key: 'coverage_est_clr_1', label: 'Est. Coverage CLR #1', description: 'Estimated clear #1 raster coverage %' },
      { key: 'coverage_est_wht_1', label: 'Est. Coverage WHT #1', description: 'Estimated white #1 raster coverage %' },
      { key: 'coverage_est_cr_1', label: 'Est. Coverage CR #1', description: 'Estimated crystal #1 raster coverage %' },
      { key: 'coverage_est_p_1', label: 'Est. Coverage P #1', description: 'Estimated pink #1 raster coverage %' },
      { key: 'coverage_est_pa_1', label: 'Est. Coverage PA #1', description: 'Estimated PA #1 raster coverage %' },
      { key: 'coverage_est_gld_6', label: 'Est. Coverage GLD #6', description: 'Estimated gold #6 raster coverage %' },
      { key: 'coverage_est_slv_6', label: 'Est. Coverage SLV #6', description: 'Estimated silver #6 raster coverage %' },
      { key: 'coverage_est_wht_6', label: 'Est. Coverage WHT #6', description: 'Estimated white #6 raster coverage %' },
      { key: 'coverage_est_p_6', label: 'Est. Coverage P #6', description: 'Estimated pink #6 raster coverage %' },
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
