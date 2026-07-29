from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(frozen=True)
class NewswireSource:
    source_id: str
    source_name: str
    feed_url: str
    publisher: str
    category: str
    poll_interval_minutes: int
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None
