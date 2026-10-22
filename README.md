# Open Holdem Manager

Local poker hand history tracker for GGPoker Rush & Cash. Parses hand histories, stores in DuckDB, computes H2N-style stats, shows graphs.

**Website:** [ohm.antonchaynik.ru](https://ohm.antonchaynik.ru)

## Download

| Platform | Download |
|----------|----------|
| macOS (Apple Silicon) | [Open-Holdem-Manager.dmg](https://github.com/AHTOOOXA/open-holdem-manager/releases/latest/download/Open-Holdem-Manager-arm64.dmg) |
| Windows | [Open-Holdem-Manager-Setup.exe](https://github.com/AHTOOOXA/open-holdem-manager/releases/latest/download/Open-Holdem-Manager-Setup.exe) |
| Linux (x86_64) | [Open-Holdem-Manager.AppImage](https://github.com/AHTOOOXA/open-holdem-manager/releases/latest/download/Open-Holdem-Manager.AppImage) |

[All releases](https://github.com/AHTOOOXA/open-holdem-manager/releases)

> **Linux note:** make the AppImage executable before running it: `chmod +x Open-Holdem-Manager.AppImage`. It needs FUSE 2 (`libfuse2`; on Ubuntu 22.04+ `sudo apt install libfuse2`). On Ubuntu 24.04+, if it closes right after launch with a sandbox error, start it with `./Open-Holdem-Manager.AppImage --no-sandbox`.

> **macOS note:** The app is not code-signed yet. macOS will show "app is damaged and can't be opened." To fix, run in Terminal after installing:
> ```
> xattr -cr /Applications/Open\ Holdem\ Manager.app
> ```
> Before you do that, [verify your download](#verify-your-download).

### Verify your download

Binaries are not code-signed yet, so check that the file was built by this repository's GitHub Actions from a tagged commit. With the [GitHub CLI](https://cli.github.com):

```bash
gh attestation verify Open-Holdem-Manager-arm64.dmg --repo AHTOOOXA/open-holdem-manager
```

Or compare the checksum with `SHA256SUMS.txt` from the same release:

```bash
shasum -a 256 Open-Holdem-Manager-arm64.dmg                    # macOS
Get-FileHash Open-Holdem-Manager-Setup.exe -Algorithm SHA256   # Windows PowerShell
sha256sum Open-Holdem-Manager.AppImage                          # Linux
```

## Privacy & network

Your hand histories and database stay on your computer. There is no account, no telemetry and no analytics. The app makes these network requests:

| When | Where | What is sent |
|---|---|---|
| On start and every 4 hours | GitHub (`api.github.com` on macOS, release files on Windows) | A normal HTTPS request to check for a newer version. No hand data. |
| You click **Download** on an update (Windows) | GitHub release files | Downloads the installer. Nothing is installed until you click **Restart to update**. |
| You click **Share** on a hand | Nothing at first | A link to `ohm.antonchaynik.ru` with the hand encoded inside it is copied to your clipboard. Whoever opens that link sends the hand to the website. Turn on anonymize first to hide your opponents' names; your own name stays. |

The local backend listens on `127.0.0.1` only.

## Using OHM with GGPoker

OHM is meant for reviewing hands after your session. It has no HUD, and it does not read the GGPoker client's memory or screen or interact with the client in any way. It only reads the hand history files you download yourself.

Close the GGPoker client before opening OHM. In October 2026 GGPoker announced that third-party poker software, including trackers such as Hand2Note, must not run alongside its client ([announcement](https://legal.ggpoker.com/blog/new-security-measures-at-ggpoker/), [Security & Ecology Policy](https://ggpoker.com/network/security-ecology-policy/)). GGPoker's rules change, and their wording on post-session use of hand histories is not spelled out. You are responsible for checking the current rules, and OHM makes no promise of compliance.

## Security

See [SECURITY.md](SECURITY.md) for how releases are built and how to report a vulnerability privately.

## Development

```bash
make setup    # install deps
make dev      # starts backend (port 4243) + frontend (port 4242)
```

## Tech Stack

- **Backend**: Python, FastAPI, DuckDB
- **Frontend**: React, TypeScript, Vite, TailwindCSS, shadcn/ui, Recharts
- **Desktop**: Electron, electron-builder

## License

Copyright © 2025-2026 Anton Safonov.

Open Holdem Manager is free software under the [GNU Affero General Public License v3.0](LICENSE). You can use, study, modify and share it. If you distribute a modified version, or run one as a network service, you must publish its source under the same license.

## Trademarks

Hand2Note, PokerTracker, Holdem Manager, GGPoker, PokerStars and other names are trademarks of their
owners. Open Holdem Manager is an independent project and is not affiliated with or endorsed by any of
them. It reads your own data (hand histories, your own Hand2Note database) for interoperability; it
contains no code or assets from other tools.
