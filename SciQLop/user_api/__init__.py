"""SciQLop user API package. This package provides the public API for SciQLop users to interact with the application.
While SciQLop internal API is subject to change, the user API is meant to be stable and should not change without notice.
All functions and classes are simplified Facades to the internal API, and are designed to be easy to use and understand.
"""

from SciQLop.backend import TimeRange

__all__ = ["TimeRange"]
