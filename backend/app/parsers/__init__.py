"""Parser registry for multi-site hand history support.

Each parser module exposes:
  - SITE_ID: int
  - SITE_CODE: str
  - SITE_NAME: str
  - detect(sample: str) -> bool
  - split_hands(content: str) -> list[str]
  - extract_hand_id(hand_text: str) -> str | None
  - parse_hand_history(hand_text: str) -> ParsedHand
"""

from app.parsers import ggpoker
from app.parsers.common import ParsedHand, _assign_positions, POSITIONS_BY_COUNT, _ZERO

PARSERS = [ggpoker]
PARSER_BY_SITE_ID = {p.SITE_ID: p for p in PARSERS}


def detect_parser(sample: str):
    """Detect which parser handles this hand history content.

    Args:
        sample: First ~500 chars of a hand history file.

    Returns:
        Parser module or None if no parser matches.
    """
    for parser in PARSERS:
        if parser.detect(sample):
            return parser
    return None
