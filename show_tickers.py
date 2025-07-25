import ccxt

exchange = ccxt.hyperliquid()
markets = exchange.load_markets()

market_data = []
for m in markets.values():
    symbol = m['symbol']
    base_name = m.get('baseName')
    name = m.get('info', {}).get('name', base_name)
    market_type = m.get('type')
    volume_str = m.get('info', {}).get('dayNtlVlm', '0')
    try:
        volume = float(volume_str)
    except:
        volume = 0.0
    market_data.append((symbol, base_name, name, market_type, volume))

# Sort by volume descending
market_data.sort(key=lambda x: x[4], reverse=True)

# Print formatted output
print(f"{'Symbol':25} {'BaseName':10} {'Name':10} {'Type':8} {'Volume'}")
print("-" * 65)
for symbol, base_name, name, market_type, volume in market_data:
    print(f"{symbol:25} {base_name:10} {name:10} {market_type:8} {volume:,.2f}")
