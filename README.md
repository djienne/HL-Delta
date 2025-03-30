# HL-Delta

HL-Delta is an automated trading system for creating and managing delta-neutral positions on Hyperliquid, a decentralized derivatives exchange.

![HL-Delta in action](image.png)
*HL-Delta placing orders to open a delta-neutral position*

## Features

- Implements delta-neutral trading strategies across spot and perpetual markets
- Automatically identifies the best funding rates for optimal yield
- Monitors and rebalances positions to maintain delta neutrality
- Handles order tracking and management
- Periodic checks to find better opportunities based on funding rates
- Graceful shutdown with position closing
- Comprehensive logging

## Requirements

- Python 3.7+
- [Hyperliquid API Python SDK](https://github.com/hyperliquid-dex/hyperliquid-python)
- `python-dotenv` package for environment variable management
- `aiohttp` for asynchronous API calls

## Setup

1. Clone the repository:

```bash
git clone https://github.com/cgaspart/HL-Delta.git
cd HL-Delta
```

2. Install the required packages:

```bash
pip install hyperliquid python-dotenv aiohttp
```

3. Create a `.env` file in the root directory with your Hyperliquid credentials:

```
HYPERLIQUID_PRIVATE_KEY=your_private_key_here
HYPERLIQUID_ADDRESS=your_eth_address_here
```

## Usage

To start the trading system:

```bash
python Delta.py
```

The system will:
1. Initialize connections to Hyperliquid
2. Check current account balances
3. Analyze funding rates across all tracked coins
4. Create delta-neutral positions for the coin with the best funding rate
5. Continuously monitor positions and funding rates
6. Rebalance as needed to maximize yield

### Testing Funding Rates

You can check current funding rates without executing any trades by running:

```bash
python test_market_data.py
```

This will display current hourly funding rates and annualized rates for all coins on Hyperliquid.

## Delta-Neutral Strategy

HL-Delta implements a capital-efficient strategy:
- Long spot positions to earn the funding rate
- Short perpetual futures positions to hedge price risk
- Automatically switches to better opportunities when funding rates change

The system targets a 70/30 spot-to-perp allocation ratio for optimal capital efficiency.

## Safety Features

- Graceful handling of API errors
- Signal handlers for clean shutdowns
- Position closing on exit
- Automatic cancellation of stale orders
- Comprehensive logging

## Project Structure

- `Delta.py` - Main trading system with delta-neutral implementation
- `test_market_data.py` - Utility to check funding rates independently
- `.env` - Configuration file for API keys (not included in repo)
- `delta.log` - Log file generated during execution

## Tracked Coins

By default, the system tracks:
- BTC
- ETH
- HYPE
- USDC

## License

MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Disclaimer

This software is for educational purposes only. Use at your own risk. Trading cryptocurrencies involves significant risk of loss and is not suitable for all investors. 
