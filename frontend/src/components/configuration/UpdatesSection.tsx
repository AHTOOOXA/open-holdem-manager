import { useEffect, useState } from 'react';
import { ArrowDownToLine, ExternalLink, RotateCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ElectronAPI {
  platform?: string;
  openExternal?: (url: string) => void;
  downloadUpdate?: () => void;
  installUpdate?: () => void;
  checkForUpdates?: () => void;
}

const RELEASES = 'https://github.com/AHTOOOXA/open-holdem-manager/releases';

export function appVersion(): string {
  return typeof __APP_VERSION__ === 'string' && __APP_VERSION__ !== '0.0.0' ? __APP_VERSION__ : 'development build';
}

export default function UpdatesSection() {
  const api = (window as unknown as { electronAPI?: ElectronAPI }).electronAPI;
  const [version, setVersion] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const canAutoUpdate = api?.platform === 'win32';

  useEffect(() => {
    const handler = (e: Event) => {
      const d = (e as CustomEvent).detail as { version: string; ready: boolean };
      setVersion(d.version);
      setReady(d.ready);
    };
    window.addEventListener('ohm-update-state', handler);
    return () => window.removeEventListener('ohm-update-state', handler);
  }, []);

  let action: React.ReactNode = null;
  if (!api) {
    action = <p className="text-sm text-muted-foreground">Updates are available in the desktop app.</p>;
  } else if (ready && canAutoUpdate) {
    action = (
      <Button onClick={() => api.installUpdate?.()}>
        <ArrowDownToLine className="size-3.5" />
        Restart to update (v{version})
      </Button>
    );
  } else if (version && canAutoUpdate) {
    action = (
      <Button onClick={() => api.downloadUpdate?.()}>
        <ArrowDownToLine className="size-3.5" />
        Download v{version}
      </Button>
    );
  } else if (version) {
    action = (
      <Button onClick={() => api.openExternal?.(`${RELEASES}/tag/v${version}`)}>
        <ExternalLink className="size-3.5" />
        Download v{version}
      </Button>
    );
  } else {
    action = (
      <Button variant="outline" onClick={() => api.checkForUpdates?.()}>
        <RotateCw className="size-3.5" />
        Check for updates
      </Button>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <dl className="flex items-baseline gap-3 text-sm">
        <dt className="text-muted-foreground">Current version</dt>
        <dd className="font-medium">{appVersion()}</dd>
      </dl>
      {version && <p className="text-sm">Version {version} is available.</p>}
      <div>{action}</div>
    </div>
  );
}
