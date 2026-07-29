from dataclasses import dataclass


@dataclass
class ListBusinessSummaryHistoryQuery:
    store_id: str
    page: int = 1
    page_size: int = 20
