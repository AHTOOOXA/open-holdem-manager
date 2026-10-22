import type { ActiveHero, HeroAccount, Site } from '@/lib/api';

/** Trim, drop blank rows and exact duplicates (first occurrence wins). */
export function normalizeNicknames(rows: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const row of rows) {
    const name = row.trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    out.push(name);
  }
  return out;
}

/** First site (in list order) that has no manual nicknames yet; falls back to the first site. */
export function firstSiteWithoutManual(sites: Site[], accounts: HeroAccount[]): string {
  const used = new Set(accounts.filter((a) => a.source === 'manual').map((a) => a.site));
  return (sites.find((s) => !used.has(s.code)) ?? sites[0])?.code ?? '';
}

export interface SiteGroup {
  site: string;
  site_name: string;
  accounts: HeroAccount[];
}

/** Group accounts of one source by site, keeping first-seen site order. */
export function groupBySite(accounts: HeroAccount[], source: 'manual' | 'auto'): SiteGroup[] {
  const groups = new Map<string, SiteGroup>();
  for (const a of accounts) {
    if (a.source !== source) continue;
    const g = groups.get(a.site) ?? { site: a.site, site_name: a.site_name, accounts: [] };
    g.accounts.push(a);
    groups.set(a.site, g);
  }
  // Detected accounts: most hands first, so the likely hero leads each card
  if (source === 'auto') {
    for (const g of groups.values()) g.accounts.sort((x, y) => y.hand_count - x.hand_count);
  }
  return [...groups.values()];
}

export function handsLabel(n: number): string {
  return `${n.toLocaleString()} ${n === 1 ? 'hand' : 'hands'}`;
}

/** Sidebar/list label: "username · Site", or a placeholder when there is no hero. */
export function heroLabel(active: Pick<ActiveHero, 'username' | 'site_name'> | null | undefined): string {
  return active ? `${active.username} · ${active.site_name}` : 'No hero yet';
}

export function heroSummary(active: ActiveHero | null): string {
  if (!active) return 'No hero yet. Import hands and OHM detects it.';
  return `Stats show ${active.username} · ${active.site_name} (${handsLabel(active.hand_count)}). Your nicknames come first, then the detected account with the most hands.`;
}
