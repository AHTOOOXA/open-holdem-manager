"""Response models of GET /api/general (H2N-style General screen).

Mirrors `GeneralResponse` / `GeneralCell` in frontend/src/lib/api-general.ts.
Numbers that H2N can show as infinity travel as the strings "inf" / "-inf";
NaN (0/0) travels as null and renders as "--".
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel

WireNumber = Optional[Union[Literal["inf", "-inf"], int, float]]


class GeneralVsUser(BaseModel):
    """The same stat counted only over hands whose matched action was against
    the user (hero). Only filled for opponents; the frontend substitutes it
    for the overall value when `sample > 50`."""

    value: WireNumber = None
    sample: int = 0
    cases: int = 0
    opps: int = 0


class GeneralCell(BaseModel):
    """One stat cell.

    Action cells: `cases` / `opps` (value = cases / opps * 100 in that order,
    sample = opps). Expression cells: `value` + `sample` (largest referenced
    sample) and their raw `inputs`. Hands: `value` = hand count, `sample` null.
    """

    kind: Literal["action", "expression"]
    value: WireNumber = None
    sample: Optional[int] = None
    cases: Optional[int] = None
    opps: Optional[int] = None
    row: Optional[str] = None
    same_as: Optional[str] = None
    inputs: Optional[dict[str, float]] = None
    vs_user: Optional[GeneralVsUser] = None


class GeneralResponse(BaseModel):
    hands: int = 0
    bb100: Optional[float] = None
    player: Optional[str] = None
    player_id: Optional[int] = None
    site: Optional[str] = None
    is_hero: bool = True
    cells: dict[str, GeneralCell] = {}
