import type { ReactNode } from 'react';
import type { SectionMeta } from './section-registry';
import AboutSection from './AboutSection';
import AliasesSection from './AliasesSection';
import ColorMarkersSection from './ColorMarkersSection';
import GameTypesSection from './GameTypesSection';
import HeroNicknamesSection from './HeroNicknamesSection';
import OtherSection from './OtherSection';
import SectionHeader from './SectionHeader';
import StatAppearanceSection from './StatAppearanceSection';
import TagsSection from './TagsSection';
import UpdatesSection from './UpdatesSection';

export interface ConfigSection extends SectionMeta {
  render: () => ReactNode;
}

/** A section without settings of its own to reset: title header + body. */
const plain = (title: string, body: ReactNode) => (
  <div>
    <SectionHeader title={title} />
    {body}
  </div>
);

/** Adding a Configuration section = one entry here. Order is display order; groups appear in order of first use. */
export const CONFIG_SECTIONS: ConfigSection[] = [
  { id: 'hero', title: 'Hero Nicknames', group: 'Players', render: () => plain('Hero Nicknames', <HeroNicknamesSection />) },
  { id: 'aliases', title: 'Aliases', group: 'Players', render: () => <AliasesSection /> },
  { id: 'game-types', title: 'Game Types', group: 'Players', render: () => <GameTypesSection /> },
  { id: 'color-markers', title: 'Color Markers', group: 'Players', render: () => <ColorMarkersSection /> },
  { id: 'tags', title: 'Marked Hand Tags', group: 'Hands', render: () => <TagsSection /> },
  { id: 'stat-appearance', title: 'Stat Appearance', group: 'Display', render: () => <StatAppearanceSection /> },
  { id: 'other', title: 'Other', group: 'Display', render: () => <OtherSection /> },
  { id: 'updates', title: 'Updates', group: 'Application', render: () => plain('Updates', <UpdatesSection />) },
  { id: 'about', title: 'About', group: 'Application', render: () => plain('About', <AboutSection />) },
];
