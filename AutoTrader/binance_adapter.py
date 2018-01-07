import datetime
import math

from binance.client import Client
from binance.enums import *

import util
from AutoTrader.adapter import Market_Adapter

FEE = 0.0025

class Binance_Adapter(Market_Adapter):
    def __init__(self, mode="ETH"):
        Market_Adapter.__init__(self, mode)
        auth = util.get_binance_auth()
        self.client = Client(**auth)

    def buy_by_symbol(self, symbol, total):
        pair = "{}{}".format(symbol, self.mode)
        price = self.get_lowest_ask(symbol)
        qty = total / price
        info = self.client.get_symbol_info(pair)
        min_total = float(info["filters"][2]["minNotional"])
        if total < min_total:
            log.warn("Could not buy %s for %s. Total too low." % (symbol, total))
            return False
        step_size = float(info["filters"][1]["stepSize"])
        qty = qty - (qty % step_size)
        try:
            # order = self.client.order_market_buy(
                # symbol=pair,
                # quantity=qty_str)
            order = self.client.create_test_order(
                symbol=pair,
                quantity=qty,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET)
        except BinanceAPIException as e:
            log.warn("Could not buy %s. Reason: %s" %(symbol, str(e)))
            return False
        return True

    def sell_by_symbol(self, symbol):
        pair = "{}{}".format(symbol, self.mode)
        qty = self.get_portfolio[symbol]
        info = self.client.get_symbol_info(pair)
        step_size = float(info["filters"][1]["stepSize"])
        qty = qty - (qty % step_size)
        minQty =  float(info["filters"][1]["minQty"])
        if qty < minQty:
            log.warn("Could not sell %s. Quantity too low." % (symbol, total))
            return False
        try:
            # order = self.client.order_market_buy(
                # symbol=pair,
                # quantity=qty_str)
            order = self.client.create_test_order(
                symbol=pair,
                quantity=qty,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET)
        except BinanceAPIException as e:
            log.warn("Could not sell %s. Reason: %s" %(symbol, str(e)))
            return False
        return True

    def get_funds(self):
        return self.get_portfolio()[self.mode]

    def get_bid_ask_mean(self, symbol):
        pair = "{}{}".format(symbol, self.mode)
        ticker = self.client.get_orderbook_ticker(symbol=pair)
        return (float(ticker[pair]["bidPrice"]) + float(ticker[pair]["askPrice"])) / 2.

    def get_highest_bid(self, symbol):
        pair = "{}{}".format(symbol, self.mode)
        ticker = self.client.get_orderbook_ticker(symbol=pair)
        return float(ticker["bidPrice"])

    def get_lowest_ask(self, symbol):
        pair = "{}{}".format(symbol, self.mode)
        ticker = self.client.get_orderbook_ticker(symbol=pair)
        return float(ticker["askPrice"])

    def get_net_worth(self):
        balances = self.get_portfolio_funds_value()
        return sum([float(b) for b in balances.values()])

    def get_portfolio_funds_value(self):
        """
        Returns all non-zero entries of the portfolio with the corresponding self.mode values.
        """
        portfolio = {}
        balances = self.get_portfolio()
        tickers = self.client.get_all_tickers()
        for coin, amount in balances.items():
            if coin == self.mode:
                portfolio[coin] = amount
                continue
            pair = "{}{}".format(coin, self.mode)
            for ticker in tickers:
                if ticker["symbol"] == pair:
                    portfolio[coin] = amount * float(ticker["price"])
        return portfolio

    def get_portfolio(self):
        """
        Returns all non-zero entries of the portfolio.
        """
        balances = self.client.get_account()["balances"]
        portfolio = {}
        for entry in balances:
            if float(entry["free"]) > 0.0:
                portfolio[entry["asset"]] = float(entry["free"])
        return portfolio

    def get_last_trade_date(self):
        """
        Returns all non-zero entries of the portfolio.
        """
        owned_coins = self.get_portfolio().keys()
        latest_timestamp = 0
        for coin in owned_coins:
            if coin == self.mode:
                continue
            pair = "{}{}".format(coin, self.mode)
            trades = self.client.get_my_trades(symbol=pair)
            max_ts = max([float(trade["time"]) for trade in trades])
            latest_timestamp = max(max_ts, latest_timestamp)
        return datetime.datetime.fromtimestamp(latest_timestamp / 1000)