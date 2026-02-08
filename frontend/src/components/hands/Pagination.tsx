export default function Pagination({
  page,
  totalPages,
  perPage,
  onPageChange,
  onPerPageChange,
}: {
  page: number;
  totalPages: number;
  perPage: number;
  onPageChange: (p: number) => void;
  onPerPageChange: (pp: number) => void;
}) {
  return (
    <div className="flex items-center justify-between py-2 px-1">
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="px-2 py-1 text-[12px] border border-border rounded hover:bg-surface-hover disabled:opacity-30 disabled:cursor-default text-text-muted"
        >
          &lsaquo; Prev
        </button>
        <span className="text-[12px] text-text-muted">
          Page {page} of {totalPages}
        </span>
        <button
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          className="px-2 py-1 text-[12px] border border-border rounded hover:bg-surface-hover disabled:opacity-30 disabled:cursor-default text-text-muted"
        >
          Next &rsaquo;
        </button>
      </div>
      <select
        value={perPage}
        onChange={(e) => onPerPageChange(Number(e.target.value))}
        className="bg-background border border-border rounded px-1.5 py-0.5 text-[12px] text-text-muted outline-none cursor-pointer"
      >
        <option value={25}>25 per page</option>
        <option value={50}>50 per page</option>
        <option value={100}>100 per page</option>
      </select>
    </div>
  );
}
