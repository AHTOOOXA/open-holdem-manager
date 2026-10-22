import { useState, useEffect } from 'react';

interface ReleaseAsset {
  name: string;
  browser_download_url: string;
}

interface ReleaseData {
  tag_name: string;
  assets: ReleaseAsset[];
  html_url: string;
}

function detectPlatform(): 'mac' | 'windows' | 'linux' | 'unknown' {
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes('mac')) return 'mac';
  if (ua.includes('win')) return 'windows';
  if (ua.includes('linux') && !ua.includes('android')) return 'linux';
  return 'unknown';
}

export default function HeroSection() {
  const [release, setRelease] = useState<ReleaseData | null>(null);
  const platform = detectPlatform();

  useEffect(() => {
    fetch('https://api.github.com/repos/AHTOOOXA/open-holdem-manager/releases/latest')
      .then((r) => r.json())
      .then((data: ReleaseData) => setRelease(data))
      .catch(() => {});
  }, []);

  const dmgUrl = release?.assets.find((a) => a.name.endsWith('.dmg'))?.browser_download_url;
  const exeUrl = release?.assets.find((a) => a.name.endsWith('.exe'))?.browser_download_url;
  const appImageUrl = release?.assets.find((a) => a.name.endsWith('.AppImage'))?.browser_download_url;
  const urls = { mac: dmgUrl, windows: exeUrl, linux: appImageUrl } as const;
  const names = { mac: 'macOS', windows: 'Windows', linux: 'Linux' } as const;
  const primaryUrl = platform === 'unknown' ? undefined : urls[platform];
  const primaryLabel = platform === 'unknown' ? 'Download' : `Download for ${names[platform]}`;
  const others = (['mac', 'windows', 'linux'] as const).filter((p) => p !== platform && urls[p]);
  const fallbackUrl = release?.html_url ?? 'https://github.com/AHTOOOXA/open-holdem-manager/releases/latest';

  return (
    <section className="relative overflow-hidden py-20 sm:py-28">
      {/* Gradient background */}
      <div className="absolute inset-0 bg-gradient-to-b from-primary/5 via-transparent to-transparent pointer-events-none" />

      <div className="relative max-w-4xl mx-auto px-4 sm:px-6 text-center">
        <h1 className="text-4xl sm:text-5xl font-bold text-text tracking-tight">
          Open Holdem Manager
        </h1>
        <p className="mt-4 text-lg sm:text-xl text-text-muted max-w-2xl mx-auto">
          Free, open-source poker hand history tracker. Parse your GGPoker hands, analyze stats, track results — all locally on your machine.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          <a
            href={primaryUrl ?? fallbackUrl}
            className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-white rounded-lg font-semibold text-lg hover:bg-primary/90 transition-colors"
          >
            {primaryLabel}
          </a>
          {platform !== 'unknown' && others.map((p) => (
            <a
              key={p}
              href={urls[p]}
              className="text-sm text-text-muted hover:text-text transition-colors"
            >
              Also available for {names[p]}
            </a>
          ))}
        </div>

        {platform === 'linux' && (
          <p className="mt-3 text-xs text-text-muted">
            After downloading: <code>chmod +x Open-Holdem-Manager.AppImage</code>
          </p>
        )}

        {release && (
          <p className="mt-3 text-xs text-text-muted">
            {release.tag_name} &middot;{' '}
            <a href={fallbackUrl} className="underline hover:text-text" target="_blank" rel="noopener noreferrer">
              Release notes
            </a>
          </p>
        )}

        <p className="mt-6 text-sm text-text-muted">
          No account needed. No cloud. Your data stays on your machine.
        </p>
      </div>
    </section>
  );
}
