# Security Policy

Open Holdem Manager handles your poker hand histories, so security reports are taken seriously.

## Reporting a vulnerability

Please **do not open a public issue**. Report privately through GitHub:
[Report a vulnerability](https://github.com/AHTOOOXA/open-holdem-manager/security/advisories/new).

Include what you found, how to reproduce it, and which version you tested. You should get a reply within 7 days.

## Supported versions

Only the latest release gets security fixes.

## How releases are built

- Releases are built by GitHub Actions from a tagged commit. Nothing is built on a personal machine.
- Every binary has a signed build-provenance attestation and a checksum in `SHA256SUMS.txt`. See [Verify your download](README.md#verify-your-download).
- The app never installs updates on its own. It checks GitHub for a new version and asks you before downloading anything.
- Binaries are **not code-signed** yet (no Apple Developer ID or Windows certificate). The attestation is the way to confirm a file came from this repository.

## What the app sends over the network

See [Privacy & network](README.md#privacy--network).
