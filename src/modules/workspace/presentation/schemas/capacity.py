# -*- coding: utf-8 -*-
"""Capacity API schemas."""

from pydantic import BaseModel, Field


class CapacityUsageResponse(BaseModel):
    """Response model for capacity usage."""

    channel_id: str = Field(..., description="Channel ID")
    file_count: int = Field(..., description="Current number of files")
    max_files: int = Field(..., description="Maximum allowed files")
    file_usage_percent: float = Field(..., description="Percentage of file limit used")
    size_bytes: int = Field(..., description="Current size in bytes")
    size_mb: float = Field(..., description="Current size in MB")
    max_size_bytes: int = Field(..., description="Maximum allowed size in bytes")
    max_size_mb: float = Field(..., description="Maximum allowed size in MB")
    size_usage_percent: float = Field(..., description="Percentage of size limit used")
    can_upload: bool = Field(..., description="Whether new uploads are allowed")
    remaining_files: int = Field(..., description="Number of files that can still be uploaded")
    remaining_mb: float = Field(..., description="MB that can still be uploaded")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "channel_id": "fileSearchStores/abc123",
                    "file_count": 25,
                    "max_files": 100,
                    "file_usage_percent": 25.0,
                    "size_bytes": 52428800,
                    "size_mb": 50.0,
                    "max_size_bytes": 524288000,
                    "max_size_mb": 500.0,
                    "size_usage_percent": 10.0,
                    "can_upload": True,
                    "remaining_files": 75,
                    "remaining_mb": 450.0,
                }
            ]
        }
    }
