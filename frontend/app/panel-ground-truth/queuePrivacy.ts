export type SafeQueueItem = {
  review_id: string; page_order: number; source_hash: string; state: string; revision: number;
  source_compatible: boolean; image_dimensions: { width: number; height: number };
  human_panels: unknown[]; image_url: string | null;
};

export function sanitizeQueue(payload: Record<string, unknown>) {
  const rawItems = Array.isArray(payload.items) ? payload.items as Record<string, unknown>[] : [];
  const items: SafeQueueItem[] = rawItems.map(item => ({
    review_id: String(item.review_id), page_order: Number(item.page_order), source_hash: String(item.source_hash),
    state: String(item.state), revision: Number(item.revision), source_compatible: Boolean(item.source_compatible),
    image_dimensions: item.image_dimensions as { width: number; height: number },
    human_panels: Array.isArray(item.human_panels) ? item.human_panels : [],
    image_url: typeof item.image_url === "string" ? item.image_url : null,
  }));
  return {
    checkpoint: payload.checkpoint, cohort: payload.cohort, total: payload.total,
    verified: payload.verified, pending: payload.pending, source_unavailable: payload.source_unavailable,
    predictions_hidden: true, panel_structure_only: true, model_calls: payload.model_calls, items,
  };
}
