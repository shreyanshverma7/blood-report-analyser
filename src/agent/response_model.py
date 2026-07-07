from typing import Optional, List
from pydantic import BaseModel


class FlaggedMarker(BaseModel):
    name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    flag: Optional[str] = None         # "high" | "low" | "normal"


class AgentResponse(BaseModel):
    summary: str                        # 1–3 sentence plain-language answer
    flagged_markers: List[FlaggedMarker] = []   # only abnormal markers relevant to the question
    recommendations: List[str] = []
    sources: List[str] = []
