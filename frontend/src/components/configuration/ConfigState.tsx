/** Loading / error placeholders shared by the Configuration sections. */
export function ConfigLoading() {
  return <p className="text-sm text-muted-foreground">Loading…</p>;
}

export function ConfigError({ error }: { error: unknown }) {
  return (
    <p role="alert" className="text-sm text-money-neg">
      Couldn't load this section. {error instanceof Error ? error.message : ''}
    </p>
  );
}
