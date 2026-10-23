import { appVersion } from './UpdatesSection';

const REPO = 'https://github.com/AHTOOOXA/open-holdem-manager';

function ExtLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="text-primary underline-offset-2 hover:underline">
      {children}
    </a>
  );
}

export default function AboutSection() {
  return (
    <div className="flex flex-col gap-5 text-sm">
      <div>
        <div className="text-base font-semibold">Open Holdem Manager</div>
        <div className="text-muted-foreground">Version {appVersion()}</div>
      </div>
      <p>
        Free software under the GNU Affero General Public License v3.0 (AGPL-3.0).{' '}
        <ExtLink href={REPO}>Source code on GitHub</ExtLink>
      </p>
      <div>
        <h3 className="mb-1 font-medium">Privacy</h3>
        <p className="text-muted-foreground">
          Your hands and database stay on your computer: no account, no telemetry. The only network request is the
          update check to GitHub.{' '}
          <ExtLink href={`${REPO}#privacy--network`}>Details</ExtLink>
        </p>
      </div>
      <div>
        <h3 className="mb-1 font-medium">Using OHM with GGPoker</h3>
        <p className="mb-2 text-muted-foreground">
          OHM is meant for reviewing hands after your session. It has no HUD, and it does not read the GGPoker client's
          memory or screen or interact with the client in any way. It only reads the hand history files you download yourself.
        </p>
        <p className="text-muted-foreground">
          Close the GGPoker client before opening OHM. In October 2026 GGPoker announced that third-party poker software,
          including trackers such as Hand2Note, must not run alongside its client (
          <ExtLink href="https://legal.ggpoker.com/blog/new-security-measures-at-ggpoker/">announcement</ExtLink>,{' '}
          <ExtLink href="https://ggpoker.com/network/security-ecology-policy/">Security &amp; Ecology Policy</ExtLink>).
          Reviewing your hands after the session, with the client closed, is how OHM is meant to be used. GGPoker's rules
          can change, so check the current ones; OHM makes no promise of compliance.
        </p>
      </div>
    </div>
  );
}
