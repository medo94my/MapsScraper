from dataclasses import dataclass


@dataclass
class Prompt:
    query: str


@dataclass
class Listing:
    name: str
    lat: float
    lon: float
    url: str
    address: str = ""
    website: str = ""
    rating: str = ""
    phone: str = ""
    query: str = ""  # originating search prompt — required for checkpointing and traceability
