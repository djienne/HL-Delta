"""
Authentication utilities for the Delta bot API.
"""

import os
import logging
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader

# Configure logging
logger = logging.getLogger("DeltaAPI.Auth")

# API key header name
API_KEY_HEADER = APIKeyHeader(name="X-API-KEY")

# Get API key from environment
API_SECRET_KEY = os.environ.get("API_SECRET_KEY")

async def verify_api_key(request: Request, api_key: str = Depends(API_KEY_HEADER)):
    """
    Verify that the API key provided in the request header matches the expected value.
    
    Args:
        request: The incoming request
        api_key: The API key from the request header
        
    Raises:
        HTTPException: If the API key is missing or invalid
    """
    if not API_SECRET_KEY:
        logger.error("API_SECRET_KEY not set in environment")
        raise HTTPException(status_code=500, detail="API authentication not configured")
        
    if api_key != API_SECRET_KEY:
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"Invalid API key attempt from {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    return True 