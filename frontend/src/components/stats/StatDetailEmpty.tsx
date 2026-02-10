export default function StatDetailEmpty() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <div className="text-text-muted text-sm">
        Click any highlighted stat to see matching hands
      </div>
      <div className="text-text-muted/50 text-xs mt-2">
        Stats with positional breakdowns can be filtered by position
      </div>
    </div>
  );
}
