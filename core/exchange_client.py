from abc import ABC, abstractmethod
from typing import Dict, List
import logging

class ExchangeClient(ABC):
    def __init__(self, config: Dict):
        self.name = config['name']
        self.api_key = config['api_key']
        self.api_secret = config['api_secret']
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    async def get_trading_pairs(self) -> List[str]:
        """Get list of available trading pairs"""
        pass

    @abstractmethod
    async def get_order_book(self, pair: str) -> Dict:
        """Get order book for a trading pair"""
        pass

    @abstractmethod
    async def execute_order(self, pair: str, side: str, amount: float, price: float) -> Dict:
        """Execute a trade order"""
        pass

class ExchangeClientFactory:
    @staticmethod
    def create(config: Dict) -> ExchangeClient:
        """Factory method to create exchange-specific client"""
        if config['type'] == 'binance':
            return BinanceClient(config)
        elif config['type'] == 'coinbase':
            return CoinbaseClient(config)
        elif config['type'] == 'kraken':
            return KrakenClient(config)
        raise ValueError(f"Unknown exchange type: {config['type']}")

class BinanceClient(ExchangeClient):
    # Implementation would go here
    pass

class CoinbaseClient(ExchangeClient):
    # Implementation would go here
    pass

class KrakenClient(ExchangeClient):
    # Implementation would go here
    pass
