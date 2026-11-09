from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    NOT_FOUND = "NOT_FOUND"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    NOT_STARTED = "NOT_STARTED"
    UNKNOWN = "UNKNOWN"
