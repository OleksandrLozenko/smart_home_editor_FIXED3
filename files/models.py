from __future__ import annotations
from dataclasses import dataclass

@dataclass
class ItemProps:
    name: str = ""
    width_px: float = 100.0
    height_px: float = 100.0
    description: str = ""
    kind: str = "object"  # "room" | "device"

class Mode:
    EDIT = "edit"
    VIEW = "view"

class Layer:
    ROOMS = "rooms"
    DEVICES = "devices"
    FURNITURE = "furniture"
