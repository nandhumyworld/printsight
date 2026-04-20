import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';

interface Suggestion {
  paper_type: string;
  width_mm: number | null;
  length_mm: number | null;
  gsm: number | null;
  job_count: number;
}

interface Props {
  printerId: number;
  onPick: (s: Suggestion) => void;
}

export function PaperSuggestSelect({ printerId, onPick }: Props) {
  const { data } = useQuery<Suggestion[]>({
    queryKey: ['paper-suggestions', printerId],
    queryFn: () => api.get(`/printers/${printerId}/paper-suggestions`).then(r => r.data.data),
  });

  if (!data || data.length === 0) return null;

  return (
    <div className="mb-3">
      <label className="mb-1 block text-xs text-muted-foreground">
        Suggest from uploaded data
      </label>
      <select
        className="w-full rounded-md border bg-card px-2 py-1.5 text-sm"
        defaultValue=""
        onChange={e => {
          const idx = parseInt(e.target.value);
          if (!isNaN(idx) && data[idx]) onPick(data[idx]);
        }}
      >
        <option value="">Choose a paper observed in print jobs…</option>
        {data.map((s, i) => (
          <option key={i} value={i}>
            {s.paper_type}
            {s.width_mm ? ` · ${s.width_mm}×${s.length_mm}mm` : ""}
            {s.gsm ? ` · ${s.gsm}gsm` : ""}
            {` (${s.job_count} jobs)`}
          </option>
        ))}
      </select>
    </div>
  );
}
