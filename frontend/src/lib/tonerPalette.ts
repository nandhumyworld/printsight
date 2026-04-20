export const TONER_COLORS: Record<string, string> = {
  paper:  "#60a5fa",
  k:      "#1f2937",
  c:      "#06b6d4",
  m:      "#ec4899",
  y:      "#facc15",
  gld:    "#d4af37",
  slv:    "#c0c0c0",
  clr:    "#a5f3fc",
  wht:    "#f8fafc",
  cr:     "#fb923c",
  p:      "#f472b6",
  pa:     "#a78bfa",
  gld_6:  "#b8860b",
  slv_6:  "#9ca3af",
  wht_6:  "#e2e8f0",
  p_6:    "#e879f9",
};

export const PAPER_COLORS = [
  "#60a5fa", "#34d399", "#f472b6", "#fbbf24", "#a78bfa",
  "#f87171", "#22d3ee", "#fb923c", "#4ade80", "#e879f9",
];

export function colorForToner(key: string): string {
  return TONER_COLORS[key.toLowerCase()] ?? "#9ca3af";
}
