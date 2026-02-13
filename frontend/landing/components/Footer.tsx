export default function Footer() {
  return (
    <footer className="border-t border-border py-8">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-text-muted">
        <span>Open Holdem Manager &middot; MIT License</span>
        <div className="flex items-center gap-4">
          <a
            href="https://github.com/AHTOOOXA/open-holdem-manager"
            className="hover:text-text transition-colors"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub
          </a>
          <a
            href="https://github.com/AHTOOOXA/open-holdem-manager/issues"
            className="hover:text-text transition-colors"
            target="_blank"
            rel="noopener noreferrer"
          >
            Issues
          </a>
          <a
            href="https://github.com/AHTOOOXA/open-holdem-manager/releases"
            className="hover:text-text transition-colors"
            target="_blank"
            rel="noopener noreferrer"
          >
            Releases
          </a>
        </div>
      </div>
    </footer>
  );
}
