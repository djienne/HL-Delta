#!/usr/bin/env python3
"""
Test script to check funding rates and market data on Hyperliquid
without executing any trades.
"""

import asyncio
import json
import aiohttp
from hyperliquid.info import Info

async def check_funding_rates():
    """Check current funding rates on Hyperliquid."""
    info = Info()

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "predictedFundings"},
            headers={"Content-Type": "application/json"}
        ) as response:
            predicted_fundings = await response.json()
    
    # Process predicted fundings data
    predicted_rates = {}
    for item in predicted_fundings:
        coin = item[0]
        venues = item[1]
        
        for venue in venues:
            venue_name = venue[0]
            if venue_name == "HlPerp":  # Hyperliquid Perp
                predicted_rates[coin] = venue[1].get("fundingRate", "0")
    return predicted_rates

def calculate_yearly_funding_rates(predicted_rates, coins=None):
    """
    Calculate the yearly funding rate for specified coins.
    
    Args:
        predicted_rates (dict): Dictionary with coin symbols as keys and funding rates as values
        coins (list): List of coin symbols to calculate yearly rates for. Default: BTC, ETH, HYPE
        
    Returns:
        dict: Dictionary with coin symbols as keys and yearly funding rates as values
    """
    if coins is None:
        coins = ["BTC", "ETH", "HYPE"]
    
    # Funding rate is per 1 hour, so multiply by 24 for daily and then by 365 for yearly
    yearly_rates = {}
    for coin in coins:
        if coin in predicted_rates:
            # Convert funding rate to float
            rate = float(predicted_rates[coin])
            # Calculate yearly rate (24 funding periods per day * 365 days)
            yearly_rate = rate * 24 * 365
            # Convert to percentage
            yearly_percentage = yearly_rate * 100
            yearly_rates[coin] = yearly_percentage
        else:
            yearly_rates[coin] = None  # Coin not found in predicted rates
    
    return yearly_rates

async def main():
    """Main function to run the test script."""
    # Get predicted funding rates
    predicted_rates = await check_funding_rates()
    
    # Calculate yearly funding rates for BTC, ETH, HYPE
    yearly_rates = calculate_yearly_funding_rates(predicted_rates)
    
    # Display results
    print("\nCurrent 1-hour funding rates:")
    for coin in ["BTC", "ETH", "HYPE"]:
        if coin in predicted_rates:
            print(f"{coin}: {predicted_rates[coin]}")
        else:
            print(f"{coin}: Not available")
    
    print("\nYearly funding rates (%):")
    for coin, rate in yearly_rates.items():
        if rate is not None:
            print(f"{coin}: {rate:.4f}%")
        else:
            print(f"{coin}: Not available")

if __name__ == "__main__":
    asyncio.run(main())

