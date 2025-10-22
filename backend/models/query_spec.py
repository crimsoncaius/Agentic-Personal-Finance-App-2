from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, Literal

from pydantic import BaseModel, Field


class QuerySpec(BaseModel):
    """Structured, read-only query specification used by AgentService.

    Notes:
    - Enforces an authoritative 10-row cap via the "limit" field validation.
    - Only allowlisted table is "entry" for v3 MVP.
    - Operators in "where" should be limited to a safe subset when executed.
    """

    select: List[Union[str, Dict]]
    from_: Literal["entry"] = Field(alias="from")
    where: Optional[Dict[str, Any]] = None
    group_by: Optional[List[str]] = None
    order_by: Optional[List[Dict[str, Literal["asc", "desc"]]]] = None
    limit: int = Field(default=10, ge=1, le=10)
    offset: int = Field(default=0, ge=0)
