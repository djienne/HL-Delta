#!/usr/bin/env python3
"""
HL-Delta: Automated trading system for Hyperliquid
"""

import os
import logging
import asyncio
import time
from dotenv import load_dotenv
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants
import eth_account
from eth_account.signers.local import LocalAccount
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Tuple

# ANSI color codes for colored terminal output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("delta.log")
    ]
)
logger = logging.getLogger("HL-Delta")


@dataclass
class SpotMarket:
    name: str
    token_id: str
    index: int
    sz_decimals: int
    wei_decimals: int
    is_canonical: bool
    full_name: str
    evm_contract: Optional[Dict] = None
    deployer_trading_fee_share: str = "0.0"
    position: Dict[str, Any] = field(default_factory=dict)
    tick_size: float = 0

@dataclass
class PerpMarket:
    name: str
    sz_decimals: int
    max_leverage: int
    index: int
    position: Dict[str, Any] = field(default_factory=dict)
    funding_rate: Optional[float] = None
    yearly_funding_rate: Optional[float] = None
    tick_size: float = 0

@dataclass
class CoinInfo:
    name: str
    spot: Optional[SpotMarket] = None
    perp: Optional[PerpMarket] = None

@dataclass
class PendingDeltaOrder:
    coin_name: str
    spot_oid: Optional[int] = None
    perp_oid: Optional[int] = None
    creation_time: float = field(default_factory=time.time)
    last_check_time: float = field(default_factory=time.time)
    spot_filled: bool = False
    perp_filled: bool = False
    max_wait_time: int = 300  # 5 minutes in seconds
    is_closing_position: bool = False  # Flag to indicate if this is for closing a position


class Delta:
    def __init__(self):
        self.config = self._load_config()
        try:
            self.tracked_coins = ["BTC", "ETH", "HYPE", "USDC"]
            self.coins: Dict[str, CoinInfo] = {}
            self.pending_orders: List[PendingDeltaOrder] = []
            
            self.account: LocalAccount = eth_account.Account.from_key(self.config["private_key"])
            self.exchange = Exchange(self.account, constants.MAINNET_API_URL, vault_address=self.config["address"])
            self.info = Info(constants.MAINNET_API_URL, skip_ws=True)
            self.api_url = constants.MAINNET_API_URL
            
            self.user_state = self.info.user_state(self.config["address"])
            self.spot_user_state = self.info.spot_user_state(self.config["address"])
            self.perp_user_state = self.account_balance = float(self.user_state['crossMarginSummary'].get('accountValue', 0))
            self.margin_summary = self.user_state["marginSummary"]
            self.address = self.config["address"]
            
            spot_meta = self.info.spot_meta()
            spot_coins = spot_meta["tokens"]
            
            perp_meta = self.info.meta()
            perp_coins = perp_meta["universe"]
            
            for coin_name in self.tracked_coins:
                self.coins[coin_name] = CoinInfo(name=coin_name)
                
                for spot_coin in spot_coins:
                    if coin_name == "BTC" and spot_coin["name"] == "UBTC":
                        self.coins[coin_name].spot = SpotMarket(
                            name=spot_coin["name"],
                            token_id=spot_coin["tokenId"],
                            index=spot_coin["index"],
                            sz_decimals=spot_coin["szDecimals"],
                            wei_decimals=spot_coin["weiDecimals"],
                            is_canonical=spot_coin["isCanonical"],
                            full_name=spot_coin["fullName"],
                            evm_contract=spot_coin.get("evmContract"),
                            deployer_trading_fee_share=spot_coin["deployerTradingFeeShare"],
                            tick_size=1
                        )
                    elif coin_name == "ETH" and spot_coin["name"] == "UETH":
                        self.coins[coin_name].spot = SpotMarket(
                            name=spot_coin["name"],
                            token_id=spot_coin["tokenId"],
                            index=spot_coin["index"],
                            sz_decimals=spot_coin["szDecimals"],
                            wei_decimals=spot_coin["weiDecimals"],
                            is_canonical=spot_coin["isCanonical"],
                            full_name=spot_coin["fullName"],
                            evm_contract=spot_coin.get("evmContract"),
                            deployer_trading_fee_share=spot_coin["deployerTradingFeeShare"],
                            tick_size=0.1
                        )
                    elif coin_name == spot_coin["name"]:
                        self.coins[coin_name].spot = SpotMarket(
                            name=spot_coin["name"],
                            token_id=spot_coin["tokenId"],
                            index=spot_coin["index"],
                            sz_decimals=spot_coin["szDecimals"],
                            wei_decimals=spot_coin["weiDecimals"],
                            is_canonical=spot_coin["isCanonical"],
                            full_name=spot_coin["fullName"],
                            evm_contract=spot_coin.get("evmContract"),
                            deployer_trading_fee_share=spot_coin["deployerTradingFeeShare"],
                            tick_size=0.001
                        )
                
                for perp_coin in perp_coins:
                    if perp_coin["name"] == coin_name:
                        self.coins[coin_name].perp = PerpMarket(
                            name=perp_coin["name"],
                            sz_decimals=perp_coin["szDecimals"],
                            max_leverage=perp_coin["maxLeverage"],
                            index=perp_coins.index(perp_coin),
                            tick_size=self.coins[coin_name].spot.tick_size
                        )
            
            self.total_raw_usd = float(self.margin_summary["totalRawUsd"])
            self.account_value = float(self.margin_summary["accountValue"])
            self.total_margin_used = float(self.margin_summary["totalMarginUsed"])
            
            for position in self.user_state.get("assetPositions", []):
                if position["type"] == "oneWay" and "position" in position:
                    pos = position["position"]
                    coin_name = pos["coin"]
                    if coin_name in self.coins and self.coins[coin_name].perp:
                        self.coins[coin_name].perp.position = {
                            "size": float(pos["szi"]),
                            "entry_price": float(pos["entryPx"]),
                            "position_value": float(pos["positionValue"]),
                            "unrealized_pnl": float(pos["unrealizedPnl"]),
                            "leverage": pos["leverage"]["value"],
                            "liquidation_price": float(pos["liquidationPx"]),
                            "cum_funding": pos["cumFunding"]["allTime"]
                        }
            
            for balance in self.spot_user_state.get("balances", []):
                if float(balance["total"]) > 0:
                    coin_name = balance["coin"]
                    
                    if coin_name == "UBTC":
                        coin_name = "BTC"
                    elif coin_name == "UETH":
                        coin_name = "ETH"
                    
                    if coin_name in self.coins and self.coins[coin_name].spot:
                        self.coins[coin_name].spot.position = {
                            "total": float(balance["total"]),
                            "hold": float(balance["hold"]),
                            "entry_ntl": float(balance["entryNtl"])
                        }
            
            logger.info(f"Initialized with account: {self.address[:8]}...")
            logger.info(f"Total account value: ${self.account_value}")
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            raise RuntimeError("Client initialization failed") from e

    def _load_config(self):
        load_dotenv()
        
        private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY")
        address = os.getenv("HYPERLIQUID_ADDRESS")
        
        if not private_key or private_key == "your_private_key_here":
            raise ValueError("HYPERLIQUID_PRIVATE_KEY not properly set in .env file")
        
        if not address or address == "your_eth_address_here":
            raise ValueError("HYPERLIQUID_ADDRESS not properly set in .env file")
        
        return {
            "private_key": private_key,
            "address": address
        }
        
    def _get_spot_account_USDC(self):
        spot_user_state = self.info.spot_user_state(self.config["address"])
        for balance in spot_user_state["balances"]:
            if balance["coin"] == "USDC":
                return float(balance["total"])
        return 0
    
    def _get_spot_price(self, coin_name):
        mid_price = self.info.all_mids()
        for key, value in mid_price.items():
            if key == coin_name:
                return float(value)
        return 0
    
    def _get_perp_price(self, coin_name):
        mid_price = self.info.all_mids()
        for key, value in mid_price.items():
            if key == coin_name:
                return float(value)
        return 0
    
    def round_size(self, coin_name: str, is_spot: bool, size: float) -> float:
        if size <= 0:
            return 0
        if is_spot:
            return round(size, self.coins[coin_name].spot.sz_decimals)
        else:
            return round(size, self.coins[coin_name].perp.sz_decimals)
    
    def round_price(self, coin_name: str, price: float) -> float:
        if coin_name not in self.coins:
            return price
            
        tick_size = self.coins[coin_name].spot.tick_size
        if tick_size <= 0:
            return price
            
        return round(price / tick_size) * tick_size
    
    def _calculate_optimal_spot_size(self, coin_name):
        spot_price = self._get_spot_price(coin_name)
        USDC_balance = self._get_spot_account_USDC()
        
        # Use only up to 90% of available USDC to account for fees and price fluctuations
        available_usdc = USDC_balance * 0.9
        
        # Ensure we have sufficient USDC (at least $10 worth)
        if available_usdc < 10:
            logger.warning(f"Insufficient USDC balance for spot purchase: ${available_usdc:.2f}")
            return 0
        
        # Calculate size based on available USDC and current price
        size = available_usdc / spot_price
        
        # Set minimum size threshold (e.g. $10 worth)
        min_size_value = 10 / spot_price
        
        if size < min_size_value:
            logger.warning(f"Calculated spot size too small: {size} (min: {min_size_value})")
            return 0
            
        rounded_size = self.round_size(coin_name, True, size)
        
        # Log the calculation for debugging
        logger.info(f"Calculated optimal spot size for {coin_name}: {size} -> rounded to {rounded_size} (USDC: ${available_usdc:.2f}, price: ${spot_price:.2f})")
        
        return rounded_size
    
    def _calculate_optimal_perp_size(self, coin_name):
        # For delta-neutral, perp size should match spot size
        spot_size = self._calculate_optimal_spot_size(coin_name)
        
        # If spot size is zero, perp size should also be zero
        if spot_size <= 0:
            return 0
        
        # Round perp size according to the coin's perp sz_decimals
        rounded_size = self.round_size(coin_name, False, spot_size)
        
        # Log the calculation for debugging
        logger.info(f"Calculated optimal perp size for {coin_name}: {spot_size} -> rounded to {rounded_size}")
        
        return rounded_size
    
    def _get_total_spot_account_value(self):
        total_spot_value = self._get_spot_account_USDC()
        for coin_name, coin_info in self.coins.items():
            if coin_info.spot and hasattr(coin_info.spot, 'position') and coin_info.spot.position and "total" in coin_info.spot.position:
                total_spot_value += coin_info.spot.position["total"] * self._get_spot_price(coin_name)
        return total_spot_value
	
    def _get_spot_account_value(self):
        spot_user_state = self.info.spot_user_state(self.config["address"])
        for balance in spot_user_state["balances"]:
            print(balance)
    
    def spot_perp_repartition(self):
        spot_value = self._get_total_spot_account_value()
        perp_value = self.perp_user_state
        return spot_value / (spot_value + perp_value)
    
    def has_delta_neutral_position(self, coin_name, error_margin=0.05):
        if coin_name not in self.coins:
            logger.warning(f"Coin {coin_name} not found in tracked coins")
            return False, 0, 0, 0
        
        coin_info = self.coins[coin_name]
        
        if not (coin_info.perp and coin_info.spot):
            logger.debug(f"{coin_name} doesn't have both perp and spot markets")
            return False, 0, 0, 0
            
        perp_size = 0
        if coin_info.perp.position:
            perp_size = coin_info.perp.position.get("size", 0)
        
        spot_size = 0
        if coin_info.spot.position:
            spot_size = coin_info.spot.position.get("total", 0)
        
        if perp_size == 0 or spot_size == 0:
            return False, perp_size, spot_size, 0
        
        is_proper_direction = perp_size < 0 and spot_size > 0
        
        abs_perp_size = abs(perp_size)
        size_diff = abs(abs_perp_size - spot_size)
        
        larger_size = max(abs_perp_size, spot_size)
        diff_percentage = (size_diff / larger_size) * 100 if larger_size > 0 else 0
        
        is_within_margin = diff_percentage <= (error_margin * 100)
        
        is_delta_neutral = is_proper_direction and is_within_margin
        
        return is_delta_neutral, perp_size, spot_size, diff_percentage
    
    def get_best_yearly_funding_rate(self):
        best_rate = 0
        best_coin = None
        for coin_name, coin_info in self.coins.items():
            if coin_info.perp and coin_info.perp.yearly_funding_rate:
                if coin_info.perp.yearly_funding_rate > best_rate:
                    best_rate = coin_info.perp.yearly_funding_rate
                    best_coin = coin_name
        return best_coin
    
    def _extract_and_track_order_ids(self, pending_order, spot_order_result, perp_order_result, coin_name, operation_type=""):
        """Helper method to extract order IDs from order responses and track their status.
        
        Args:
            pending_order: The PendingDeltaOrder object to update
            spot_order_result: The result from the spot order API call
            perp_order_result: The result from the perp order API call
            coin_name: Name of the coin
            operation_type: Type of operation (opening/closing) for logging
        
        Returns:
            bool: True if tracking started or orders filled, False otherwise
        """
        # Extract order IDs from spot order response
        if spot_order_result and spot_order_result.get('status') == 'ok':
            spot_response = spot_order_result.get('response', {}).get('data', {}).get('statuses', [{}])[0]
            if 'filled' in spot_response:
                pending_order.spot_filled = True
                pending_order.spot_oid = int(spot_response['filled']['oid'])
                logger.info(f"Spot {operation_type} order for {coin_name} filled immediately with oid: {pending_order.spot_oid}")
            elif 'resting' in spot_response:
                pending_order.spot_oid = int(spot_response['resting']['oid'])
                logger.info(f"Spot {operation_type} order for {coin_name} resting with oid: {pending_order.spot_oid}")
        
        # Extract order IDs from perp order response
        if perp_order_result and perp_order_result.get('status') == 'ok':
            perp_response = perp_order_result.get('response', {}).get('data', {}).get('statuses', [{}])[0]
            if 'filled' in perp_response:
                pending_order.perp_filled = True
                pending_order.perp_oid = int(perp_response['filled']['oid'])
                logger.info(f"Perp {operation_type} order for {coin_name} filled immediately with oid: {pending_order.perp_oid}")
            elif 'resting' in perp_response:
                pending_order.perp_oid = int(perp_response['resting']['oid'])
                logger.info(f"Perp {operation_type} order for {coin_name} resting with oid: {pending_order.perp_oid}")
        
        # Determine if we need to track these orders or if they're already complete
        if (pending_order.spot_oid or pending_order.perp_oid) and (not pending_order.spot_filled or not pending_order.perp_filled):
            self.pending_orders.append(pending_order)
            logger.info(f"Added pending {operation_type} position for {coin_name} to tracking")
            return True
        elif pending_order.spot_filled and pending_order.perp_filled:
            # If both orders filled immediately, we don't need to track
            logger.info(f"Both {operation_type} orders for {coin_name} filled immediately")
            return True
        else:
            logger.warning(f"Failed to create or track {operation_type} orders for {coin_name}")
            return False
    
    async def create_delta_position(self, coin_name):
        if coin_name not in self.coins:
            logger.warning(f"Coin {coin_name} not found in tracked coins")
            return False
        
        coin_info = self.coins[coin_name]
        
        if not (coin_info.perp and coin_info.spot):
            logger.warning(f"{coin_name} doesn't have both perp and spot markets")
            return False
        
        # Check if we already have a delta-neutral position for this coin
        is_delta_neutral, perp_size, spot_size, _ = self.has_delta_neutral_position(coin_name)
        if is_delta_neutral:
            logger.info(f"Already have a delta-neutral position for {coin_name} - perp: {perp_size}, spot: {spot_size}")
            return True
        
        try:
            price = self._get_spot_price(coin_name)
            if price <= 0:
                logger.error(f"Invalid price for {coin_name}: {price}")
                return False
            
            # Get optimal sizes for spot and perp
            spot_size = self._calculate_optimal_spot_size(coin_name)
            if spot_size <= 0:
                logger.error(f"Calculated spot size for {coin_name} is not positive: {spot_size}")
                return False
                
            perp_size = spot_size  # For delta-neutral, perp size equals spot size
            
            # Validate the sizes after rounding
            if spot_size <= 0 or perp_size <= 0:
                logger.error(f"Invalid position size after rounding for {coin_name}: spot={spot_size}, perp={perp_size}")
                return False
            
            # Calculate minimum size based on $10 value
            min_size_value = 10 / price
            if spot_size < min_size_value:
                logger.warning(f"Calculated position size for {coin_name} is too small: {spot_size} < {min_size_value}")
                logger.warning(f"Current price: ${price}, minimum position value: $10")
                return False
                
            # Ensure we have enough USDC for this purchase
            required_usdc = spot_size * price
            available_usdc = self._get_spot_account_USDC()
            if required_usdc > available_usdc * 0.95:  # Leave 5% buffer
                logger.warning(f"Insufficient USDC for {coin_name} position: need ${required_usdc:.2f}, have ${available_usdc:.2f}")
                return False
                
            tick_size = coin_info.spot.tick_size
            spot_limit_price = self.round_price(coin_name, price + tick_size)
            perp_limit_price = self.round_price(coin_name, price - tick_size)
                
            # Create a new pending order to track
            pending_order = PendingDeltaOrder(coin_name=coin_name, is_closing_position=False)
            spot_order_result = None
            perp_order_result = None
                
            logger.info(f"Creating spot buy limit order for {coin_name}: {spot_size} @ {spot_limit_price}")
            if coin_name == "BTC":
                spot_name = "UBTC"
            elif coin_name == "ETH":
                spot_name = "UETH"
            else:
                spot_name = coin_name
                
            spot_pair = f"{spot_name}/USDC"
            
            spot_order_result = self.exchange.order(spot_pair, True, spot_size, spot_limit_price, {"limit": {"tif": "Gtc"}})
            logger.info(f"Spot order result: {spot_order_result}")
            
            logger.info(f"Creating perp short limit order for {coin_name}: {-perp_size} @ {perp_limit_price}")
            perp_order_result = self.exchange.order(coin_name, False, perp_size, perp_limit_price, {"limit": {"tif": "Gtc"}})
            logger.info(f"Perp order result: {perp_order_result}")
            
            # Use the shared helper method to track orders
            return self._extract_and_track_order_ids(
                pending_order, 
                spot_order_result, 
                perp_order_result, 
                coin_name, 
                "opening"
            )
            
        except Exception as e:
            logger.error(f"Error creating delta-neutral position for {coin_name}: {e}")
            return False
    
    async def check_pending_orders(self):
        """Check the status of all pending orders and handle accordingly."""
        if not self.pending_orders:
            return
        
        current_time = time.time()
        orders_to_remove = []
        
        for pending_order in self.pending_orders:
            # Skip if checked recently (less than 30 seconds ago)
            if current_time - pending_order.last_check_time < 30:
                continue
                
            pending_order.last_check_time = current_time
            
            operation_type = "closing" if pending_order.is_closing_position else "opening"
            logger.info(f"Checking pending {operation_type} delta position for {pending_order.coin_name}")
            
            # Check if both orders are already filled
            if pending_order.spot_filled and pending_order.perp_filled:
                logger.info(f"Both {operation_type} orders for {pending_order.coin_name} are filled, removing from pending")
                orders_to_remove.append(pending_order)
                continue
            
            # Check if we've waited too long
            if current_time - pending_order.creation_time > pending_order.max_wait_time:
                logger.warning(f"{operation_type.capitalize()} orders for {pending_order.coin_name} have been pending for too long, cancelling")
                
                if not pending_order.spot_filled and pending_order.spot_oid:
                    try:
                        if pending_order.coin_name == "BTC":
                            spot_name = "UBTC"
                        elif pending_order.coin_name == "ETH":
                            spot_name = "UETH"
                        else:
                            spot_name = pending_order.coin_name
                            
                        spot_pair = f"{spot_name}/USDC"
                        cancel_result = self.exchange.cancel(spot_pair, pending_order.spot_oid)
                        logger.info(f"Cancelled spot {operation_type} order for {pending_order.coin_name}: {cancel_result}")
                    except Exception as e:
                        logger.error(f"Error cancelling spot {operation_type} order for {pending_order.coin_name}: {e}")
                
                if not pending_order.perp_filled and pending_order.perp_oid:
                    try:
                        cancel_result = self.exchange.cancel(pending_order.coin_name, pending_order.perp_oid)
                        logger.info(f"Cancelled perp {operation_type} order for {pending_order.coin_name}: {cancel_result}")
                    except Exception as e:
                        logger.error(f"Error cancelling perp {operation_type} order for {pending_order.coin_name}: {e}")
                
                orders_to_remove.append(pending_order)
                
                # Only try to recreate a delta position if we were opening, not closing
                if not pending_order.is_closing_position:
                    logger.info(f"Recreating delta position for {pending_order.coin_name}")
                    await self.create_delta_position(pending_order.coin_name)
                else:
                    logger.info(f"Not attempting to recreate closing position for {pending_order.coin_name}")
                continue
            
            # Check current order status from exchange
            try:
                # Check spot order status if not already filled
                if not pending_order.spot_filled and pending_order.spot_oid:
                    if pending_order.coin_name == "BTC":
                        spot_name = "UBTC"
                    elif pending_order.coin_name == "ETH":
                        spot_name = "UETH"
                    else:
                        spot_name = pending_order.coin_name
                        
                    # Check if spot order is filled by checking order status
                    spot_order_response = self.exchange.info.query_order_by_oid(self.address, pending_order.spot_oid)
                    logger.debug(f"Spot order status response: {spot_order_response}")
                    
                    # Check if the order is still open based on the status field
                    if spot_order_response.get('status') == 'order':
                        order_data = spot_order_response.get('order', {})
                        if order_data.get('status') != 'open':
                            # Order is not open anymore, assume filled
                            logger.info(f"Spot {operation_type} order for {pending_order.coin_name} is no longer open, marking as filled")
                            pending_order.spot_filled = True
                    else:
                        # If the response doesn't contain the order, it might have been filled
                        logger.info(f"Spot {operation_type} order for {pending_order.coin_name} not found, marking as filled")
                        pending_order.spot_filled = True
                
                # Check perp order status if not already filled
                if not pending_order.perp_filled and pending_order.perp_oid:
                    # Check if perp order is filled by checking order status
                    perp_order_response = self.exchange.info.query_order_by_oid(self.address, pending_order.perp_oid)
                    logger.debug(f"Perp order status response: {perp_order_response}")
                    
                    # Check if the order is still open based on the status field
                    if perp_order_response.get('status') == 'order':
                        order_data = perp_order_response.get('order', {})
                        if order_data.get('status') != 'open':
                            # Order is not open anymore, assume filled
                            logger.info(f"Perp {operation_type} order for {pending_order.coin_name} is no longer open, marking as filled")
                            pending_order.perp_filled = True
                    else:
                        # If the response doesn't contain the order, it might have been filled
                        logger.info(f"Perp {operation_type} order for {pending_order.coin_name} not found, marking as filled")
                        pending_order.perp_filled = True
                
                # If both are now filled, remove from pending
                if pending_order.spot_filled and pending_order.perp_filled:
                    logger.info(f"Both {operation_type} orders for {pending_order.coin_name} are now filled, removing from pending")
                    orders_to_remove.append(pending_order)
                
            except Exception as e:
                logger.error(f"Error checking {operation_type} order status for {pending_order.coin_name}: {e}")
        
        # Remove processed orders
        for order in orders_to_remove:
            self.pending_orders.remove(order)
    
    def close_delta_position(self, coin_name):
        if coin_name not in self.coins:
            logger.warning(f"Coin {coin_name} not found in tracked coins")
            return False
        
        coin_info = self.coins[coin_name]
        
        if not (coin_info.perp and coin_info.spot):
            logger.warning(f"{coin_name} doesn't have both perp and spot markets")
            return False
        
        try:
            # Check if we have positions to close
            is_delta_neutral, perp_size, spot_size, _ = self.has_delta_neutral_position(coin_name)
            
            if not is_delta_neutral:
                logger.warning(f"No delta-neutral position for {coin_name} to close")
                return False
            
            price = self._get_spot_price(coin_name)
            if price <= 0:
                logger.error(f"Invalid price for {coin_name}: {price}")
                return False
            
            # For closing, we reverse the orders:
            # - Sell the spot position
            # - Buy back (cover) the short perp position
            
            tick_size = coin_info.spot.tick_size
            spot_limit_price = self.round_price(coin_name, price - tick_size)  # Sell slightly below market
            perp_limit_price = self.round_price(coin_name, price + tick_size)  # Buy slightly above market
            
            # Create a new pending order to track
            pending_order = PendingDeltaOrder(coin_name=coin_name, is_closing_position=True)
            spot_order_result = None
            perp_order_result = None
            
            # For spot, we need to sell what we have
            if spot_size > 0:
                logger.info(f"Creating spot sell limit order for {coin_name}: {spot_size} @ {spot_limit_price}")
                
                if coin_name == "BTC":
                    spot_name = "UBTC"
                elif coin_name == "ETH":
                    spot_name = "UETH"
                else:
                    spot_name = coin_name
                    
                spot_pair = f"{spot_name}/USDC"
                
                # For sell orders, side is False (sell)
                rounded_spot_size = self.round_size(coin_name, True, spot_size)
                spot_order_result = self.exchange.order(spot_pair, False, rounded_spot_size, spot_limit_price, {"limit": {"tif": "Gtc"}})
                logger.info(f"Spot sell order result: {spot_order_result}")
            
            # For perp, we need to buy back our short position
            if perp_size < 0:
                # Convert negative size to positive for buy order
                buy_size = abs(perp_size)
                logger.info(f"Creating perp buy limit order to close short for {coin_name}: {buy_size} @ {perp_limit_price}")
                
                # For buy orders, side is True (buy)
                perp_order_result = self.exchange.order(coin_name, True, buy_size, perp_limit_price, {"limit": {"tif": "Gtc"}})
                logger.info(f"Perp buy order result: {perp_order_result}")
            
            # Use the shared helper method to track orders
            return self._extract_and_track_order_ids(
                pending_order, 
                spot_order_result, 
                perp_order_result, 
                coin_name, 
                "closing"
            )
            
        except Exception as e:
            logger.error(f"Error closing delta-neutral position for {coin_name}: {e}")
            return False
    
    async def close_all_delta_positions(self):
        """Close all active delta-neutral positions across all tracked coins."""
        logger.info("Attempting to close all delta-neutral positions...")
        
        closed_positions = 0
        for coin_name in self.tracked_coins:
            if coin_name == "USDC":
                continue
                
            is_delta_neutral, _, _, _ = self.has_delta_neutral_position(coin_name)
            if is_delta_neutral:
                logger.info(f"Closing delta-neutral position for {coin_name}...")
                result = self.close_delta_position(coin_name)
                if result:
                    logger.info(f"Successfully closed delta-neutral position for {coin_name}")
                    closed_positions += 1
                else:
                    logger.warning(f"Failed to close delta-neutral position for {coin_name}")
        
        if closed_positions > 0:
            logger.info(f"Successfully closed {closed_positions} delta-neutral positions")
        else:
            logger.info("No delta-neutral positions were closed")
            
        return closed_positions > 0
    
    async def exit_program(self, close_positions=True):
        """Safely exit the delta trading program.
        
        Args:
            close_positions: Whether to close all open delta positions before exiting
        """
        logger.info("Initiating shutdown sequence...")
        
        if close_positions:
            logger.info("Closing all delta-neutral positions before exit...")
            await self.close_all_delta_positions()
        
        logger.info("Delta trading system shutting down")
        # Additional cleanup if needed
        return True
            
    async def execute_best_delta_strategy(self):
        best_coin = self.get_best_yearly_funding_rate()
        if not best_coin:
            logger.warning("No coin with positive funding rate found")
            return False
            
        is_delta_neutral, _, _, _ = self.has_delta_neutral_position(best_coin)
        if is_delta_neutral:
            logger.info(f"Already have delta-neutral position for {best_coin}")
            return False
            
        logger.info(f"Creating delta-neutral position for {best_coin} with best funding rate: {self.coins[best_coin].perp.yearly_funding_rate:.4f}%")
        return await self.create_delta_position(best_coin)
    
    def check_allocation(self):
        ratio = self.spot_perp_repartition()
        if ratio < 0.665:  # 0.7 - 5%
            spot_value = self._get_total_spot_account_value()
            perp_value = self.perp_user_state
            amount_to_transfer = (perp_value * 0.7 - spot_value * 0.3) / 1.0
            logger.info(f"Allocation mismatch: {ratio:.2f} (target: 0.7)")
            logger.info(f"Recommended transfer from perp to spot: ${amount_to_transfer:.2f}")
            return False
        elif ratio > 0.735:  # 0.7 + 5%
            spot_value = self._get_total_spot_account_value()
            perp_value = self.perp_user_state
            amount_to_transfer = (spot_value * 0.3 - perp_value * 0.7) / 1.0
            logger.info(f"Allocation mismatch: {ratio:.2f} (target: 0.7)")
            logger.info(f"Recommended transfer from spot to perp: ${amount_to_transfer:.2f}")
            return False
        return True
    
    def display_position_info(self):
        """Display detailed information about tracked coins and positions."""
        logger.info(f"\n{Colors.BOLD}{Colors.CYAN}Tracked Coins Information:{Colors.RESET}")
        for coin_name, coin_info in self.coins.items():
            if coin_name == "USDC":
                continue
                
            logger.info(f"\n{Colors.BOLD}{Colors.YELLOW}{coin_name} Markets:{Colors.RESET}")
            
            is_delta_neutral, perp_size, spot_size, diff_percentage = self.has_delta_neutral_position(coin_name)
            
            status_color = Colors.GREEN if is_delta_neutral else Colors.RED
            status_text = "✅ DELTA NEUTRAL" if is_delta_neutral else "❌ NOT DELTA NEUTRAL"
            logger.info(f"  Delta Status: {status_color}{status_text}{Colors.RESET}")
            
            if perp_size != 0 or spot_size != 0:
                logger.info(f"    Perp Size: {Colors.MAGENTA}{perp_size:.4f}{Colors.RESET}")
                logger.info(f"    Spot Size: {Colors.CYAN}{spot_size:.4f}{Colors.RESET}")
                diff_color = Colors.GREEN if diff_percentage < 5 else Colors.YELLOW if diff_percentage < 10 else Colors.RED
                logger.info(f"    Difference: {diff_color}{diff_percentage:.2f}%{Colors.RESET}")
            
            if coin_info.perp:
                logger.info(f"    {Colors.BOLD}Perpetual Market:{Colors.RESET}")
                logger.info(f"      Index: {coin_info.perp.index}")
                logger.info(f"      Size Decimals: {coin_info.perp.sz_decimals}")
                logger.info(f"      Max Leverage: {coin_info.perp.max_leverage}x")
                logger.info(f"      Tick Size: {coin_info.perp.tick_size}")
                
                if coin_info.perp.funding_rate is not None:
                    logger.info(f"      Current Funding Rate: {Colors.CYAN}{coin_info.perp.funding_rate:.8f}{Colors.RESET}")
                    
                    # Color funding rate based on value
                    rate_color = Colors.RED
                    if coin_info.perp.yearly_funding_rate >= 20:
                        rate_color = Colors.GREEN + Colors.BOLD
                    elif coin_info.perp.yearly_funding_rate >= 10:
                        rate_color = Colors.GREEN
                    elif coin_info.perp.yearly_funding_rate >= 5:
                        rate_color = Colors.YELLOW
                        
                    logger.info(f"      Yearly Funding Rate: {rate_color}{coin_info.perp.yearly_funding_rate:.4f}%{Colors.RESET}")
                
                if coin_info.perp.position:
                    pos = coin_info.perp.position
                    logger.info(f"      Position: {Colors.MAGENTA}{pos['size']:.4f}{Colors.RESET} @ ${Colors.YELLOW}{pos['entry_price']:.2f}{Colors.RESET}")
                    logger.info(f"      Position Value: ${Colors.CYAN}{pos['position_value']:.2f}{Colors.RESET}")
                    
                    # Color PnL based on profit/loss
                    pnl_color = Colors.GREEN if pos['unrealized_pnl'] > 0 else Colors.RED
                    logger.info(f"      Unrealized PnL: {pnl_color}${pos['unrealized_pnl']:.2f}{Colors.RESET}")
                    
                    logger.info(f"      Leverage: {Colors.YELLOW}{pos['leverage']}x{Colors.RESET}")
                    logger.info(f"      Liquidation Price: ${Colors.RED}{pos['liquidation_price']:.2f}{Colors.RESET}")
                    logger.info(f"      Cumulative Funding: {pos['cum_funding']}")
                else:
                    logger.info(f"      Position: {Colors.RED}None{Colors.RESET}")
            
            if coin_info.spot:
                logger.info(f"    {Colors.BOLD}Spot Market:{Colors.RESET}")
                logger.info(f"      Name: {coin_info.spot.name} ({coin_info.spot.full_name})")
                logger.info(f"      Token ID: {coin_info.spot.token_id}")
                logger.info(f"      Index: {coin_info.spot.index}")
                logger.info(f"      Size Decimals: {coin_info.spot.sz_decimals}")
                logger.info(f"      Wei Decimals: {coin_info.spot.wei_decimals}")
                logger.info(f"      Tick Size: {coin_info.spot.tick_size}")
                if coin_info.spot.position:
                    pos = coin_info.spot.position
                    logger.info(f"      Balance: {Colors.CYAN}{pos['total']:.4f}{Colors.RESET}")
                    logger.info(f"      On Hold: {Colors.YELLOW}{pos['hold']:.4f}{Colors.RESET}")
                    logger.info(f"      Entry Value: ${Colors.GREEN}{pos['entry_ntl']:.2f}{Colors.RESET}")
                else:
                    logger.info(f"      Position: {Colors.RED}None{Colors.RESET}")
        
        ratio = self.spot_perp_repartition()
        ratio_color = Colors.GREEN if 0.665 <= ratio <= 0.735 else Colors.YELLOW if 0.6 <= ratio <= 0.8 else Colors.RED
        logger.info(f"  Spot Perp Repartition: {ratio_color}{ratio:.4f}{Colors.RESET} (target: {Colors.CYAN}0.7{Colors.RESET})")
        
        allocation_ok = self.check_allocation()
        if allocation_ok == False:
            logger.info(f"{Colors.RED}Portfolio allocation is not within target ratio (70% spot / 30% perp){Colors.RESET}")
        
        # Show the best funding rate coin (but don't try to create a position here)
        best_coin = self.get_best_yearly_funding_rate()
        if best_coin:
            rate_color = Colors.RED
            rate = self.coins[best_coin].perp.yearly_funding_rate
            if rate >= 20:
                rate_color = Colors.GREEN + Colors.BOLD
            elif rate >= 10:
                rate_color = Colors.GREEN
            elif rate >= 5:
                rate_color = Colors.YELLOW
                
            logger.info(f"Best funding rate coin: {Colors.YELLOW}{best_coin}{Colors.RESET} with rate {rate_color}{rate:.4f}%{Colors.RESET}")

    async def check_hourly_funding_rates(self):
        """
        Checks funding rates at 10 minutes before each hour.
        If current annual yield < 5%, find a better delta position.
        """
        try:
            # Get current time
            now = time.localtime()
            
            # Only run this function at 10 minutes before the hour (e.g., 8:50, 9:50, etc.)
            if now.tm_min != 50:
                return
                
            logger.info(f"\n{Colors.BOLD}{Colors.CYAN}Running scheduled check for better funding rates (10 minutes before the hour){Colors.RESET}")
            
            # Get current funding rates
            from test_market_data import check_funding_rates, calculate_yearly_funding_rates
            
            funding_rates = await check_funding_rates()
            yearly_rates = calculate_yearly_funding_rates(funding_rates, self.tracked_coins)
            
            # Update funding rates in our coin data structure
            for coin_name, rate in funding_rates.items():
                if coin_name in self.coins and self.coins[coin_name].perp:
                    self.coins[coin_name].perp.funding_rate = float(rate)
            
            for coin_name, rate in yearly_rates.items():
                if coin_name in self.coins and self.coins[coin_name].perp:
                    self.coins[coin_name].perp.yearly_funding_rate = rate
                    rate_color = Colors.RED
                    if rate >= 20:
                        rate_color = Colors.GREEN + Colors.BOLD
                    elif rate >= 10:
                        rate_color = Colors.GREEN
                    elif rate >= 5:
                        rate_color = Colors.YELLOW
                    logger.info(f"Updated {Colors.YELLOW}{coin_name}{Colors.RESET} yearly funding rate: {rate_color}{rate:.4f}%{Colors.RESET}")
            
            # Refresh user state to get latest positions
            try:
                self.user_state = self.info.user_state(self.config["address"])
                self.spot_user_state = self.info.spot_user_state(self.config["address"])
                
                # Update perp positions
                for position in self.user_state.get("assetPositions", []):
                    if position["type"] == "oneWay" and "position" in position:
                        pos = position["position"]
                        coin_name = pos["coin"]
                        if coin_name in self.coins and self.coins[coin_name].perp:
                            self.coins[coin_name].perp.position = {
                                "size": float(pos["szi"]),
                                "entry_price": float(pos["entryPx"]),
                                "position_value": float(pos["positionValue"]),
                                "unrealized_pnl": float(pos["unrealizedPnl"]),
                                "leverage": pos["leverage"]["value"],
                                "liquidation_price": float(pos["liquidationPx"]),
                                "cum_funding": pos["cumFunding"]["allTime"]
                            }
                
                # Update spot positions
                for balance in self.spot_user_state.get("balances", []):
                    if float(balance["total"]) > 0:
                        coin_name = balance["coin"]
                        
                        if coin_name == "UBTC":
                            coin_name = "BTC"
                        elif coin_name == "UETH":
                            coin_name = "ETH"
                        
                        if coin_name in self.coins and self.coins[coin_name].spot:
                            self.coins[coin_name].spot.position = {
                                "total": float(balance["total"]),
                                "hold": float(balance["hold"]),
                                "entry_ntl": float(balance["entryNtl"])
                            }
                            
                logger.info(f"{Colors.GREEN}Successfully refreshed position data{Colors.RESET}")
                
                # Display detailed position information in hourly check
                self.display_position_info()
                
            except Exception as e:
                logger.error(f"{Colors.RED}Error refreshing position data: {e}{Colors.RESET}")
            
            # Find current active delta neutral position
            current_position_coin = None
            for coin_name in self.tracked_coins:
                if coin_name == "USDC":
                    continue
                    
                is_delta_neutral, perp_size, spot_size, _ = self.has_delta_neutral_position(coin_name)
                if is_delta_neutral:
                    current_position_coin = coin_name
                    logger.info(f"{Colors.GREEN}Found active delta-neutral position on {Colors.YELLOW}{coin_name}{Colors.GREEN} with perp size {Colors.MAGENTA}{perp_size}{Colors.GREEN} and spot size {Colors.CYAN}{spot_size}{Colors.RESET}")
                    break
            
            if not current_position_coin:
                logger.info(f"{Colors.YELLOW}No active delta-neutral position found.{Colors.RESET}")
                # Find the best coin and create a new position if its rate is >= 5%
                best_coin = self.get_best_yearly_funding_rate()
                if best_coin and self.coins[best_coin].perp.yearly_funding_rate >= 5.0:
                    logger.info(f"{Colors.GREEN}Creating new delta-neutral position for {Colors.YELLOW}{best_coin}{Colors.GREEN} with rate {Colors.CYAN}{self.coins[best_coin].perp.yearly_funding_rate:.4f}%{Colors.RESET}")
                    await self.create_delta_position(best_coin)
                else:
                    logger.info(f"{Colors.YELLOW}No coin with funding rate >= 5% found. Waiting until next check.{Colors.RESET}")
                return
            
            # Check if current position has yield < 5%
            current_yield = self.coins[current_position_coin].perp.yearly_funding_rate
            rate_color = Colors.RED
            if current_yield >= 20:
                rate_color = Colors.GREEN + Colors.BOLD
            elif current_yield >= 10:
                rate_color = Colors.GREEN
            elif current_yield >= 5:
                rate_color = Colors.YELLOW
                
            logger.info(f"Current delta-neutral position: {Colors.YELLOW}{current_position_coin}{Colors.RESET} with yield: {rate_color}{current_yield:.4f}%{Colors.RESET}")
            
            if current_yield is None or current_yield < 5.0:
                logger.info(f"{Colors.YELLOW}Current yield for {current_position_coin} is below 5% (or None). Looking for better options...{Colors.RESET}")
                
                # Find coin with highest funding rate
                best_coin = self.get_best_yearly_funding_rate()
                
                if not best_coin or (best_coin and self.coins[best_coin].perp.yearly_funding_rate < 5.0):
                    logger.info(f"{Colors.YELLOW}No coin with funding rate >= 5% found. Keeping current position for now.{Colors.RESET}")
                    return
                
                # Make sure the best coin is different from current coin and has better rate
                if best_coin == current_position_coin:
                    logger.info(f"{Colors.YELLOW}{current_position_coin} still has the best funding rate but it's below 5%.{Colors.RESET}")
                    return
                    
                best_rate = self.coins[best_coin].perp.yearly_funding_rate
                best_rate_color = Colors.RED
                if best_rate >= 20:
                    best_rate_color = Colors.GREEN + Colors.BOLD
                elif best_rate >= 10:
                    best_rate_color = Colors.GREEN
                elif best_rate >= 5:
                    best_rate_color = Colors.YELLOW
                    
                logger.info(f"{Colors.GREEN}Found better coin: {Colors.YELLOW}{best_coin}{Colors.GREEN} with yield: {best_rate_color}{best_rate:.4f}%{Colors.RESET}")
                
                # Close current position and open new one
                logger.info(f"{Colors.YELLOW}Closing current position on {current_position_coin}...{Colors.RESET}")
                close_result = self.close_delta_position(current_position_coin)
                
                if close_result:
                    logger.info(f"{Colors.GREEN}Successfully initiated closing of position on {current_position_coin}{Colors.RESET}")
                    # Wait for closing orders to be processed
                    close_pending = True
                    max_wait = 180  # 3 minutes max wait
                    start_time = time.time()
                    
                    while close_pending and time.time() - start_time < max_wait:
                        logger.info(f"{Colors.YELLOW}Waiting for closing orders to complete...{Colors.RESET}")
                        # Check pending orders
                        await self.check_pending_orders()
                        
                        # Check if any pending orders are for the current coin and are closing
                        close_pending = any(order.coin_name == current_position_coin and order.is_closing_position for order in self.pending_orders)
                        
                        if close_pending:
                            await asyncio.sleep(10)  # Wait 10 seconds before checking again
                    
                    if close_pending:
                        logger.warning(f"{Colors.YELLOW}Closing position on {current_position_coin} is taking too long. Will continue with opening new position.{Colors.RESET}")
                    
                    logger.info(f"{Colors.GREEN}Creating new delta-neutral position for {best_coin}...{Colors.RESET}")
                    create_result = await self.create_delta_position(best_coin)
                    
                    if create_result:
                        logger.info(f"{Colors.GREEN}Successfully initiated new delta-neutral position on {best_coin}{Colors.RESET}")
                    else:
                        logger.error(f"{Colors.RED}Failed to create new delta-neutral position on {best_coin}{Colors.RESET}")
                else:
                    logger.error(f"{Colors.RED}Failed to close position on {current_position_coin}{Colors.RESET}")
            else:
                logger.info(f"{Colors.GREEN}Current yield for {current_position_coin} is above 5%. No action needed.{Colors.RESET}")
                
        except Exception as e:
            logger.error(f"{Colors.RED}Error checking hourly funding rates: {e}{Colors.RESET}", exc_info=True)
    
    async def start(self):
        logger.info(f"{Colors.BOLD}{Colors.GREEN}Starting Delta trading system...{Colors.RESET}")
        
        logger.info(f"{Colors.BOLD}{Colors.CYAN}Account Summary:{Colors.RESET}")
        logger.info(f"  Total Value: ${Colors.GREEN}{self.total_raw_usd:.2f}{Colors.RESET}")
        logger.info(f"  Account Value: ${Colors.GREEN}{self.account_value:.2f}{Colors.RESET}")
        logger.info(f"  Margin Used: ${Colors.YELLOW}{self.total_margin_used:.2f}{Colors.RESET}")
        logger.info(f"  Perp Account Value: ${Colors.MAGENTA}{self.perp_user_state:.2f}{Colors.RESET}")
        logger.info(f"  Spot USDC Value: ${Colors.CYAN}{self._get_spot_account_USDC():.2f}{Colors.RESET}")
        logger.info(f"  Spot Account Value: ${Colors.BLUE}{self._get_total_spot_account_value():.2f}{Colors.RESET}")
        
        from test_market_data import check_funding_rates, calculate_yearly_funding_rates
        
        funding_rates = await check_funding_rates()
        yearly_rates = calculate_yearly_funding_rates(funding_rates)
        
        for coin_name, rate in funding_rates.items():
            if coin_name in self.coins and self.coins[coin_name].perp:
                self.coins[coin_name].perp.funding_rate = float(rate)
        
        for coin_name, rate in yearly_rates.items():
            if coin_name in self.coins and self.coins[coin_name].perp:
                self.coins[coin_name].perp.yearly_funding_rate = rate
        
        self.display_position_info()
        
        allocation_ok = self.check_allocation()
        if allocation_ok == False:
            logger.info(f"{Colors.RED}Portfolio allocation is not within target ratio (70% spot / 30% perp){Colors.RESET}")
        
        # Check if we should create a new delta-neutral position
        best_coin = self.get_best_yearly_funding_rate()
        if best_coin:
            rate = self.coins[best_coin].perp.yearly_funding_rate
            rate_color = Colors.RED
            if rate >= 20:
                rate_color = Colors.GREEN + Colors.BOLD
            elif rate >= 10:
                rate_color = Colors.GREEN
            elif rate >= 5:
                rate_color = Colors.YELLOW
                
            logger.info(f"{Colors.CYAN}Best funding rate coin for new position: {Colors.YELLOW}{best_coin}{Colors.CYAN} with rate {rate_color}{rate:.4f}%{Colors.RESET}")
            
            # Check if we already have a position for this coin
            is_delta_neutral, perp_size, spot_size, _ = self.has_delta_neutral_position(best_coin)
            if not is_delta_neutral and rate >= 5.0:
                logger.info(f"{Colors.GREEN}Creating delta-neutral position for {Colors.YELLOW}{best_coin}...{Colors.RESET}")
                result = await self.execute_best_delta_strategy()
                if result:
                    logger.info(f"{Colors.GREEN}Successfully created delta-neutral position for {Colors.YELLOW}{best_coin}{Colors.RESET}")
                else:
                    logger.warning(f"{Colors.RED}Failed to create delta-neutral position for {Colors.YELLOW}{best_coin}{Colors.RESET}")
            elif is_delta_neutral:
                logger.info(f"{Colors.GREEN}Already have a delta-neutral position for {Colors.YELLOW}{best_coin}{Colors.RESET}")
            else:
                logger.info(f"{Colors.YELLOW}Best funding rate ({rate:.4f}%) is below 5% threshold, not creating position{Colors.RESET}")

        # Main loop
        while True:
            try:
                # Check pending orders
                await self.check_pending_orders()
                
                # Check hourly funding rates (runs only at HH:50)
                await self.check_hourly_funding_rates()
                
                # Add other periodic tasks here
                
                # Sleep for a bit
                await asyncio.sleep(30)
            except KeyboardInterrupt:
                logger.info(f"{Colors.YELLOW}Keyboard interrupt detected in main loop{Colors.RESET}")
                break
            except Exception as e:
                logger.error(f"{Colors.RED}Error in main loop: {e}{Colors.RESET}", exc_info=True)
                await asyncio.sleep(60)  # Sleep longer on error


def setup_signal_handlers(delta_instance):
    """Set up signal handlers for graceful shutdown."""
    import signal
    import sys
    
    # Global flag to indicate shutdown is in progress
    shutdown_in_progress = False
    
    def signal_handler(sig, frame):
        nonlocal shutdown_in_progress
        
        if shutdown_in_progress:
            logger.info("Forced exit requested. Exiting immediately.")
            sys.exit(1)
            
        shutdown_in_progress = True
        logger.info(f"Received signal {sig}, shutting down...")
        logger.info("Press Ctrl+C again to force immediate exit")
        
        # Don't exit here, just set the flag for the main loop to check
        # The main loop handles the graceful shutdown
        # This causes KeyboardInterrupt to be raised in the main event loop
        raise KeyboardInterrupt()
    
    signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Handle termination signal
    
    logger.info("Signal handlers set up for graceful shutdown")


async def main():
    delta = None
    try:
        delta = Delta()
        setup_signal_handlers(delta)
        await delta.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected, closing positions...")
        if delta:
            try:
                # Make sure to close positions before exiting
                logger.info("Attempting to close all positions...")
                await delta.close_all_delta_positions()
                logger.info("Position closing complete")
                await delta.exit_program(close_positions=False)  # Already closed positions above
            except Exception as e:
                logger.error(f"Error during shutdown: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error running Delta: {e}", exc_info=True)
        if delta:
            try:
                await delta.exit_program(close_positions=True)
            except Exception as shutdown_e:
                logger.error(f"Error during shutdown: {shutdown_e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This will catch the KeyboardInterrupt at the top level after signal handling
        logger.info("Exiting due to keyboard interrupt")
    except SystemExit:
        # Handle the SystemExit exception from sys.exit() in the signal handler
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
