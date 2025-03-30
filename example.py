#!/usr/bin/env python3
"""
Example script showing how to use the Delta class with config.json
"""

import asyncio
import os
import sys
import logging
from Delta import Delta, logger

# Ensure we have environment variables set
if not os.getenv("HYPERLIQUID_PRIVATE_KEY") or not os.getenv("HYPERLIQUID_ADDRESS"):
    print("Error: Environment variables HYPERLIQUID_PRIVATE_KEY and HYPERLIQUID_ADDRESS must be set")
    print("Example:")
    print("export HYPERLIQUID_PRIVATE_KEY=your_private_key_here")
    print("export HYPERLIQUID_ADDRESS=your_eth_address_here")
    sys.exit(1)

async def main():
    try:
        # Create Delta instance with config.json
        delta = Delta(config_path="config.json")
        
        # Display account and position information
        delta.display_position_info()
        
        # Get funding rates for tracked coins
        from test_market_data import check_funding_rates, calculate_yearly_funding_rates
        
        print("\nFetching current funding rates...")
        funding_rates = await check_funding_rates()
        yearly_rates = calculate_yearly_funding_rates(funding_rates, delta.tracked_coins)
        
        print("\nCurrent Funding Rates:")
        for coin_name in delta.tracked_coins:
            if coin_name != "USDC" and coin_name in yearly_rates:
                yearly_rate = yearly_rates[coin_name]
                if yearly_rate is not None:
                    print(f"{coin_name}: {yearly_rate:.4f}% APR")
                else:
                    print(f"{coin_name}: N/A")
        
        # Check for the best funding rate
        best_coin = delta.get_best_yearly_funding_rate()
        if best_coin:
            print(f"\nBest funding rate coin: {best_coin} ({delta.coins[best_coin].perp.yearly_funding_rate:.4f}% APR)")
        
        # Example: Check allocation
        allocation_ok = delta.check_allocation()
        if not allocation_ok:
            print(f"\nAllocation mismatch from target {delta.spot_allocation_pct*100:.0f}% spot / {delta.perp_allocation_pct*100:.0f}% perp ratio")
        
        print("\nExample completed successfully")
        
    except Exception as e:
        logger.error(f"Error running example: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}") 