import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';

interface SkippedRow {
  row_number: number;
  reason: string;
}

interface BatchDetail {
  id: number;
  filename: string | null;
  source: string;
  uploaded_at: string;
  status: string;
  rows_total: number;
  rows_imported: number;
  rows_skipped: number;
  skipped_details: SkippedRow[];
}

interface Props {
  printerId: string;
  batchId: number | null;
  onClose: () => void;
}

const ROWS_PER_REASON = 100;

/** Group skipped rows by reason — a bad import is usually one reason repeated many times. */
function groupByReason(rows: SkippedRow[]): [string, number[]][] {
  const groups = new Map<string, number[]>();
  for (const r of rows) {
    const list = groups.get(r.reason);
    if (list) list.push(r.row_number);
    else groups.set(r.reason, [r.row_number]);
  }
  return [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
}

export function UploadBatchDrawer({ printerId, batchId, onClose }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['upload-batch', printerId, batchId],
    queryFn: () =>
      api.get(`/printers/${printerId}/uploads/${batchId}`).then(r => r.data.data as BatchDetail),
    enabled: batchId !== null,
  });

  if (batchId === null) return null;

  const groups = data ? groupByReason(data.skipped_details) : [];

  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-black/20" onClick={onClose}>
      <div
        className="h-full w-full max-w-md overflow-y-auto bg-card p-6 shadow-xl border-l"
        onClick={e => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="text-lg font-bold truncate">{data?.filename || 'Upload'}</h3>
            {data && (
              <p className="text-xs text-muted-foreground">
                {data.source} · {new Date(data.uploaded_at).toLocaleString()}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-2xl text-muted-foreground hover:text-foreground leading-none"
          >
            ×
          </button>
        </div>

        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {isError && <p className="text-sm text-red-600">Could not load this upload.</p>}

        {data && (
          <>
            <div className="mb-4 grid grid-cols-3 gap-3 text-sm">
              <div className="rounded-lg border bg-muted/30 p-3 text-center">
                <div className="text-lg font-bold">{data.rows_total}</div>
                <div className="text-xs text-muted-foreground">Total</div>
              </div>
              <div className="rounded-lg border bg-muted/30 p-3 text-center">
                <div className="text-lg font-bold text-green-600">{data.rows_imported}</div>
                <div className="text-xs text-muted-foreground">Imported</div>
              </div>
              <div className="rounded-lg border bg-muted/30 p-3 text-center">
                <div className="text-lg font-bold text-amber-600">{data.rows_skipped}</div>
                <div className="text-xs text-muted-foreground">Skipped</div>
              </div>
            </div>

            {data.skipped_details.length === 0 ? (
              <p className="rounded-md border bg-muted/30 px-3 py-4 text-center text-sm text-muted-foreground">
                All rows imported successfully.
              </p>
            ) : (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold">Skipped rows</h4>
                {groups.map(([reason, rowNumbers]) => (
                  <details key={reason} className="rounded-md border">
                    <summary className="cursor-pointer px-3 py-2 text-sm flex items-center justify-between gap-2">
                      <span className="min-w-0 break-words">{reason}</span>
                      <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                        ×{rowNumbers.length}
                      </span>
                    </summary>
                    <div className="border-t px-3 py-2 text-xs text-muted-foreground">
                      rows {rowNumbers.slice(0, ROWS_PER_REASON).join(', ')}
                      {rowNumbers.length > ROWS_PER_REASON &&
                        ` +${rowNumbers.length - ROWS_PER_REASON} more`}
                    </div>
                  </details>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
