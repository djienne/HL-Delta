"""
Status routes for the Delta bot API.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# Logger
logger = logging.getLogger("StatusRoutes")

# Router
router = APIRouter()

# Bot instance (set at runtime)
bot = None

class StatusResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

@router.get("")
async def get_status():
    """Get the current status of the bot and its positions."""
    if not bot:
        raise HTTPException(status_code=500, detail="Bot instance not initialized")
    
    try:
        positions = []
        
        # Extract position information
        for coin_name, coin_info in bot.coins.items():
            if coin_info.spot and hasattr(coin_info.spot, 'position') and coin_info.spot.position:
                # Has a spot position
                spot_position = coin_info.spot.position
                positions.append({
                    "coin": coin_name,
                    "type": "spot",
                    "size": spot_position.get("total", 0),
                    "value": spot_position.get("entry_ntl", 0),
                    "hold": spot_position.get("hold", 0)
                })
            
            if coin_info.perp and hasattr(coin_info.perp, 'position') and coin_info.perp.position:
                # Has a perp position
                perp_position = coin_info.perp.position
                positions.append({
                    "coin": coin_name,
                    "type": "perp",
                    "size": perp_position.get("size", 0),
                    "entry_price": perp_position.get("entry_price", 0),
                    "position_value": perp_position.get("position_value", 0),
                    "unrealized_pnl": perp_position.get("unrealized_pnl", 0),
                    "leverage": perp_position.get("leverage", 0),
                    "liquidation_price": perp_position.get("liquidation_price", 0),
                    "funding": perp_position.get("cum_funding", 0)
                })
        
        # Get funding rates if available
        funding_rates = {}
        for coin_name, coin_info in bot.coins.items():
            if coin_info.perp and hasattr(coin_info.perp, 'funding_rate') and coin_info.perp.funding_rate:
                funding_rates[coin_name] = {
                    "hourly": coin_info.perp.funding_rate,
                    "yearly": coin_info.perp.yearly_funding_rate if hasattr(coin_info.perp, 'yearly_funding_rate') else None
                }
        
        # Account information
        account_info = {
            "address": bot.address,
            "total_value": bot.account_value,
            "margin_used": bot.total_margin_used if hasattr(bot, 'total_margin_used') else None,
            "total_raw_usd": bot.total_raw_usd if hasattr(bot, 'total_raw_usd') else None
        }
        
        # Return all status information
        return StatusResponse(
            success=True,
            message="Bot status retrieved successfully",
            data={
                "running": hasattr(bot, '_is_running') and bot._is_running,
                "positions": positions,
                "funding_rates": funding_rates,
                "account": account_info,
                "pending_orders": len(bot.pending_orders) if hasattr(bot, 'pending_orders') else 0
            }
        )
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/funding-rates")
async def get_funding_rates():
    """Get the current funding rates for all tracked coins."""
    if not bot:
        raise HTTPException(status_code=500, detail="Bot instance not initialized")
    
    try:
        # Fetch current funding rates
        await bot.check_hourly_funding_rates()
        
        funding_rates = {}
        for coin_name, coin_info in bot.coins.items():
            if coin_info.perp and hasattr(coin_info.perp, 'funding_rate') and coin_info.perp.funding_rate:
                funding_rates[coin_name] = {
                    "hourly": coin_info.perp.funding_rate,
                    "yearly": coin_info.perp.yearly_funding_rate if hasattr(coin_info.perp, 'yearly_funding_rate') else None
                }
        
        return StatusResponse(
            success=True,
            message="Funding rates retrieved successfully",
            data={"funding_rates": funding_rates}
        )
    except Exception as e:
        logger.error(f"Error getting funding rates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions")
async def get_positions():
    """Get all current positions."""
    if not bot:
        raise HTTPException(status_code=500, detail="Bot instance not initialized")
    
    try:
        positions = []
        
        # Extract position information
        for coin_name, coin_info in bot.coins.items():
            if coin_info.spot and hasattr(coin_info.spot, 'position') and coin_info.spot.position:
                # Has a spot position
                spot_position = coin_info.spot.position
                positions.append({
                    "coin": coin_name,
                    "type": "spot",
                    "size": spot_position.get("total", 0),
                    "value": spot_position.get("entry_ntl", 0),
                    "hold": spot_position.get("hold", 0)
                })
            
            if coin_info.perp and hasattr(coin_info.perp, 'position') and coin_info.perp.position:
                # Has a perp position
                perp_position = coin_info.perp.position
                positions.append({
                    "coin": coin_name,
                    "type": "perp",
                    "size": perp_position.get("size", 0),
                    "entry_price": perp_position.get("entry_price", 0),
                    "position_value": perp_position.get("position_value", 0),
                    "unrealized_pnl": perp_position.get("unrealized_pnl", 0),
                    "leverage": perp_position.get("leverage", 0),
                    "liquidation_price": perp_position.get("liquidation_price", 0),
                    "funding": perp_position.get("cum_funding", 0)
                })
        
        return StatusResponse(
            success=True,
            message="Positions retrieved successfully",
            data={"positions": positions}
        )
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 