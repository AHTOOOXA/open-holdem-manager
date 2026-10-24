import type { ReactNode } from 'react';
import type { SectionMeta } from './section-registry';
import HeroNicknamesSection from './HeroNicknamesSection';
import UpdatesSection from './UpdatesSection';
import AboutSection from './AboutSection';
import OtherSection from './OtherSection';

export interface ConfigSection extends SectionMeta {
  render: () => ReactNode;
}

/** Adding a Configuration section = one entry here. Order is display order; groups appear in order of first use. */
export const CONFIG_SECTIONS: ConfigSection[] = [
  { id: 'hero', title: 'Hero Nicknames', group: 'Players', render: () => <HeroNicknamesSection /> },
  { id: 'other', title: 'Other', group: 'Application', render: () => <OtherSection /> },
  { id: 'updates', title: 'Updates', group: 'Application', render: () => <UpdatesSection /> },
  { id: 'about', title: 'About', group: 'Application', render: () => <AboutSection /> },
];
