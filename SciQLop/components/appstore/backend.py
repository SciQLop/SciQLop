from __future__ import annotations

import json

from PySide6.QtCore import QObject, Slot

MOCK_PACKAGES = [
    {"name": "AMDA Provider", "type": "plugin", "author": "IRAP", "description": "Access AMDA data directly in SciQLop", "tags": ["data-provider", "amda"], "version": "1.2.0", "stars": 42, "downloads": 156},
    {"name": "Wavelet Analysis", "type": "plugin", "author": "LPP", "description": "Continuous wavelet transform for time series", "tags": ["analysis", "wavelets"], "version": "0.9.1", "stars": 28, "downloads": 89},
    {"name": "CDAWeb Provider", "type": "plugin", "author": "NASA/GSFC", "description": "CDAWeb data access integration", "tags": ["data-provider", "cdaweb"], "version": "2.0.0", "stars": 21, "downloads": 203},
    {"name": "Boundary Detection", "type": "plugin", "author": "LPP", "description": "Automatic detection of magnetopause and bow shock crossings", "tags": ["analysis", "boundaries", "mms"], "version": "0.3.0", "stars": 9, "downloads": 34},
    {"name": "MMS Mission Study", "type": "workspace", "author": "IRAP", "description": "Pre-configured workspace for MMS magnetospheric data analysis", "tags": ["mms", "magnetosphere"], "version": "1.0.0", "stars": 15, "downloads": 67},
    {"name": "Solar Wind Analysis", "type": "workspace", "author": "Community", "description": "Workspace for solar wind parameter studies", "tags": ["solar-wind", "heliophysics"], "version": "1.1.0", "stars": 12, "downloads": 45},
    {"name": "Solar Wind Tutorial", "type": "example", "author": "Community", "description": "Step-by-step introduction to solar wind data analysis with SciQLop", "tags": ["tutorial", "solar-wind", "beginner"], "version": "1.0.0", "stars": 33, "downloads": 312},
    {"name": "Virtual Products Guide", "type": "example", "author": "IRAP", "description": "Learn to create derived quantities using virtual products", "tags": ["tutorial", "virtual-product"], "version": "1.0.0", "stars": 19, "downloads": 128},
    {"name": "MMS Reconnection Events", "type": "example", "author": "Community", "description": "Catalog of magnetic reconnection events observed by MMS", "tags": ["mms", "reconnection", "catalog"], "version": "2.1.0", "stars": 24, "downloads": 91},
]


class AppStoreBackend(QObject):
    """Python backend exposed to the AppStore page via QWebChannel."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

    @Slot(str, result=str)
    def list_packages(self, category: str = "") -> str:
        if category:
            filtered = [p for p in MOCK_PACKAGES if p["type"] == category]
        else:
            filtered = MOCK_PACKAGES
        return json.dumps(filtered)

    @Slot(str, result=str)
    def get_package_detail(self, name: str) -> str:
        for p in MOCK_PACKAGES:
            if p["name"] == name:
                return json.dumps(p)
        return "null"

    @Slot(result=str)
    def list_tags(self) -> str:
        tags = set()
        for p in MOCK_PACKAGES:
            tags.update(p.get("tags", []))
        return json.dumps(sorted(tags))
