"""
Configuration routes for the Delta bot API.
"""

import json
import logging
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# Logger
logger = logging.getLogger("ConfigRoutes")

# Router
router = APIRouter()

# Bot instance (set at runtime)
bot = None

class ConfigResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

@router.get("")
async def get_config():
    """Get the current configuration of the bot."""
    if not bot:
        raise HTTPException(status_code=500, detail="Bot instance not initialized")
    
    try:
        # Return the current configuration
        config = {}
        
        # Only return serializable configuration
        if hasattr(bot, 'config'):
            config = bot.config.copy()
            
        # Additional configuration from the bot (excluding private keys)
        if hasattr(bot, 'tracked_coins'):
            config['tracked_coins'] = bot.tracked_coins
        
        return ConfigResponse(
            success=True,
            message="Configuration retrieved successfully",
            data={"config": config}
        )
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update")
async def update_config(
    updates: Dict[str, Any] = Body(..., description="Configuration updates")
):
    """Update the bot's configuration."""
    if not bot:
        raise HTTPException(status_code=500, detail="Bot instance not initialized")
    
    try:
        # Validate the updates
        for key, value in updates.items():
            # Don't update the private key
            if key == "private_key" or key == "address":
                continue
            
            # Apply the update
            if key == "tracked_coins" and isinstance(value, list):
                bot.tracked_coins = value
            elif hasattr(bot, 'config') and isinstance(bot.config, dict):
                bot.config[key] = value
        
        return ConfigResponse(
            success=True,
            message="Configuration updated successfully",
            data={"updated_keys": [k for k in updates.keys() if k not in ["private_key", "address"]]}
        )
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracked-coins")
async def get_tracked_coins():
    """Get the list of tracked coins."""
    if not bot:
        raise HTTPException(status_code=500, detail="Bot instance not initialized")
    
    try:
        return ConfigResponse(
            success=True,
            message="Tracked coins retrieved successfully",
            data={"tracked_coins": bot.tracked_coins}
        )
    except Exception as e:
        logger.error(f"Error getting tracked coins: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add-coin/{coin}")
async def add_tracked_coin(coin: str):
    """Add a coin to the tracked coins list."""
    if not bot:
        raise HTTPException(status_code=500, detail="Bot instance not initialized")
    
    try:
        # Check if the coin is already tracked
        if coin in bot.tracked_coins:
            return ConfigResponse(
                success=False,
                message=f"Coin {coin} is already tracked"
            )
        
        # Add the coin to the tracked coins list
        bot.tracked_coins.append(coin)
        
        return ConfigResponse(
            success=True,
            message=f"Added {coin} to tracked coins",
            data={"tracked_coins": bot.tracked_coins}
        )
    except Exception as e:
        logger.error(f"Error adding tracked coin: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/remove-coin/{coin}")
async def remove_tracked_coin(coin: str):
    """Remove a coin from the tracked coins list."""
    if not bot:
        raise HTTPException(status_code=500, detail="Bot instance not initialized")
    
    try:
        # Check if the coin is in the tracked coins list
        if coin not in bot.tracked_coins:
            return ConfigResponse(
                success=False,
                message=f"Coin {coin} is not in the tracked coins list"
            )
        
        # Remove the coin from the tracked coins list
        bot.tracked_coins.remove(coin)
        
        return ConfigResponse(
            success=True,
            message=f"Removed {coin} from tracked coins",
            data={"tracked_coins": bot.tracked_coins}
        )
    except Exception as e:
        logger.error(f"Error removing tracked coin: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 