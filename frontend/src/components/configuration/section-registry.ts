/** Pure helpers for the Configuration screen's section list (no React, unit-tested). */
export interface SectionMeta {
  id: string;
  title: string;
  group: string;
}

/** The section with this id, or the first one when the id is missing or unknown. */
export function findSection<T extends SectionMeta>(sections: readonly T[], id: string | undefined): T {
  return sections.find((s) => s.id === id) ?? sections[0];
}

/** Sections grouped in order of first appearance; order inside a group follows the array. */
export function groupSections<T extends SectionMeta>(sections: readonly T[]): { group: string; sections: T[] }[] {
  const out: { group: string; sections: T[] }[] = [];
  for (const s of sections) {
    let g = out.find((x) => x.group === s.group);
    if (!g) {
      g = { group: s.group, sections: [] };
      out.push(g);
    }
    g.sections.push(s);
  }
  return out;
}
