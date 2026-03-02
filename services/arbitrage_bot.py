import asyncio
import logging
import time
from typing import Dict, List, Optional
from decimal import Decimal
import httpx

from core.database import execute_sql
from core.payment_processor import CryptoPaymentProcessor
from core.exchange_client import ExchangeClientFactory

class ArbitrageBot:
    def __init__(self, config: Dict):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.rate_limiter = RateLimiter(
            max_requests=config.get('max_requests_per_minute', 60),
            period=60
        )
        self.payment_processor = CryptoPaymentProcessor(config['wallet'])
        self.exchanges = [
            ExchangeClientFactory.create(exchange_config)
            for exchange_config in config['exchanges']
        ]
        self.min_profit_threshold = Decimal(config.get('min_profit_threshold', '0.002'))
        self.max_trade_amount = Decimal(config.get('max_trade_amount', '0.1'))

    async def find_opportunities(self) -> List[Dict]:
        """Find profitable arbitrage opportunities across exchanges"""
        opportunities = []
        
        try:
            pairs = await self.fetch_common_pairs()
            for pair in pairs:
                order_books = await self.fetch_order_books(pair)
                opportunity = self.analyze_order_books(pair, order_books)
                if opportunity and opportunity['profit_pct'] >= self.min_profit_threshold:
                    opportunities.append(opportunity)
        except Exception as e:
            self.logger.error(f"Error finding opportunities: {e}")
            
        return opportunities

    async def fetch_common_pairs(self) -> List[str]:
        """Get common trading pairs across all exchanges"""
        pair_sets = []
        for exchange in self.exchanges:
            await self.rate_limiter.wait()
            try:
                pairs = await exchange.get_trading_pairs()
                pair_sets.append(set(pairs))
            except Exception as e:
                self.logger.warning(f"Failed to get pairs from {exchange.name}: {e}")
                continue
                
        return list(set.intersection(*pair_sets)) if pair_sets else []

    async def fetch_order_books(self, pair: str) -> Dict[str, Dict]:
        """Get order books for a pair from all exchanges"""
        order_books = {}
        tasks = []
        
        for exchange in self.exchanges:
            await self.rate_limiter.wait()
            tasks.append(exchange.get_order_book(pair))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for exchange, result in zip(self.exchanges, results):
            if not isinstance(result, Exception):
                order_books[exchange.name] = result
                
        return order_books

    def analyze_order_books(self, pair: str, order_books: Dict[str, Dict]) -> Optional[Dict]:
        """Analyze order books for arbitrage opportunities"""
        best_bid = {'price': Decimal('-Infinity'), 'exchange': None}
        best_ask = {'price': Decimal('Infinity'), 'exchange': None}
        
        for exchange_name, book in order_books.items():
            if 'bids' in book and book['bids']:
                bid_price = Decimal(book['bids'][0][0])
                if bid_price > best_bid['price']:
                    best_bid = {'price': bid_price, 'exchange': exchange_name}
                    
            if 'asks' in book and book['asks']:
                ask_price = Decimal(book['asks'][0][0])
                if ask_price < best_ask['price']:
                    best_ask = {'price': ask_price, 'exchange': exchange_name}
                    
        if best_bid['exchange'] is None or best_ask['exchange'] is None:
            return None
            
        if best_bid['exchange'] == best_ask['exchange']:
            return None
            
        profit = best_bid['price'] - best_ask['price']
        profit_pct = profit / best_ask['price']
        
        if profit_pct > self.min_profit_threshold:
            return {
                'pair': pair,
                'buy_exchange': best_ask['exchange'],
                'sell_exchange': best_bid['exchange'],
                'buy_price': float(best_ask['price']),
                'sell_price': float(best_bid['price']),
                'profit_pct': float(profit_pct),
                'timestamp': int(time.time())
            }
        return None

    async def execute_trade(self, opportunity: Dict) -> Dict:
        """Execute arbitrage trade with safety checks"""
        try:
            # Verify opportunity again right before execution
            buy_exchange = next(
                (e for e in self.exchanges if e.name == opportunity['buy_exchange']),
                None
            )
            sell_exchange = next(
                (e for e in self.exchanges if e.name == opportunity['sell_exchange']),
                None
            )
            
            if not buy_exchange or not sell_exchange:
                raise ValueError("Invalid exchange configuration")

            # Get fresh order books
            await self.rate_limiter.wait()
            buy_book = await buy_exchange.get_order_book(opportunity['pair'])
            sell_book = await sell_exchange.get_order_book(opportunity['pair'])
            
            # Re-analyze with latest data
            fresh_opportunity = self.analyze_order_books(
                opportunity['pair'],
                {
                    opportunity['buy_exchange']: buy_book,
                    opportunity['sell_exchange']: sell_book
                }
            )
            
            if not fresh_opportunity:
                raise ValueError("Arbitrage opportunity no longer available")

            # Calculate trade amount (minimum of best asks/bids sizes and max limit)
            buy_amount = min(
                Decimal(buy_book['asks'][0][1]), 
                Decimal(sell_book['bids'][0][1]),
                self.max_trade_amount
            )
            
            # Execute buy order
            buy_result = await buy_exchange.execute_order(
                pair=opportunity['pair'],
                side='buy',
                amount=float(buy_amount),
                price=float(Decimal(buy_book['asks'][0][0]))
            )
            
            # Execute sell order
            sell_result = await sell_exchange.execute_order(
                pair=opportunity['pair'],
                side='sell',
                amount=float(buy_amount),  # Same amount as purchased
                price=float(Decimal(sell_book['bids'][0][0]))
            )
            
            # Record transaction
            net_amount = (Decimal(sell_result['total']) - Decimal(buy_result['total']))
            fee = Decimal(buy_result.get('fee', '0')) + Decimal(sell_result.get('fee', '0'))
            net_profit = net_amount - fee
            
            await self.record_transaction(
                buy_order=buy_result,
                sell_order=sell_result,
                opportunity=opportunity,
                fee=fee,
                net_profit=net_profit
            )
            
            return {
                'success': True,
                'net_profit': float(net_profit),
                'buy_order_id': buy_result['order_id'],
                'sell_order_id': sell_result['order_id']
            }
            
        except Exception as e:
            self.logger.error(f"Failed to execute trade: {e}")
            return {
                'success': False,
                'error': str(e),
                'opportunity': opportunity
            }

    async def record_transaction(self, buy_order: Dict, sell_order: Dict, 
                                opportunity: Dict, fee: Decimal, net_profit: Decimal) -> None:
        """Record transaction in database"""
        try:
            await execute_sql(
                f"""
                INSERT INTO arbitrage_transactions (
                    timestamp, pair, 
                    buy_exchange, sell_exchange, 
                    buy_price, sell_price,
                    amount, fee, net_profit,
                    buy_order_id, sell_order_id,
                    status
                ) VALUES (
                    {int(time.time())},
                    '{opportunity['pair']}',
                    '{opportunity['buy_exchange']}',
                    '{opportunity['sell_exchange']}',
                    {float(opportunity['buy_price'])},
                    {float(opportunity['sell_price'])},
                    {float(buy_order['amount'])},
                    {float(fee)},
                    {float(net_profit)},
                    '{buy_order['order_id']}',
                    '{sell_order['order_id']}',
                    'completed'
                )
                """
            )
            self.logger.info(f"Recorded arbitrage transaction: {buy_order['order_id']}")
            
        except Exception as e:
            self.logger.error(f"Failed to record transaction: {e}")
