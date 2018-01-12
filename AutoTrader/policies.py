import datetime

import query
import util
from database import DatabaseConnection

log = util.setup_logger(__name__)
auth = util.get_postgres_auth()
db = DatabaseConnection(**auth)

K = 4
GROWTH_HOURS = 24
# if a coin has less than STAGNATION_THRESHOLD price growth in STAGNATION_HOURS hours
# it is considered stagnating
MIN_HOLD_HOURS = 23
USE_STAGNATION_DETECTION = True
STAGNATION_HOURS = 6
STAGNATION_THRESHOLD = 0.045
NEVER_SELL = ["BNB"]

def __sell_and_spendings__(adapter, growths):
    """
    Calculates which coins to sell and how much o spend on other coins based on a dict of growths and subreddits.
    """
    assert len(growths) == K
    owned_coins = adapter.get_portfolio_funds_value()
    owned_coins.pop(adapter.mode, None)
    spend = {}
    # prevent selling and rebuying the same coin
    owned_symbols = list(owned_coins.keys())

    # start out with complete list
    sell = owned_symbols
    # remove never sell
    sell = [s for s in sell if s not in NEVER_SELL]
    # dont sell when total would be under threshold or not held long enough
    at_least_owned_since = datetime.datetime.utcnow() - datetime.timedelta(hours=MIN_HOLD_HOURS)
    non_dust_coins = 0
    for coin in list(sell):
        if not adapter.can_sell(coin):
            log.info("Not selling %s because market does not allow it." % (coin))
            sell.remove(coin)
        elif adapter.get_last_buy_date(coin) > at_least_owned_since:
            log.info("Not selling %s because it is not owned since more than %shrs." % (coin, MIN_HOLD_HOURS))
            sell.remove(coin)
            non_dust_coins += 1
    # dont sell those coins which are not stagnating
    if USE_STAGNATION_DETECTION:
        for symbol in list(sell):
            subs = util.get_subs_for_symbol(adapter.coin_name_array, symbol)
            assert len(subs) == 1
            if not __stagnation_detection__(subs[0]):
                sell.remove(symbol)
                log.info("Not selling %s because its value is rising." % (symbol))

    buy_count = K - non_dust_coins
    buy_coins = [util.get_symbol_for_sub(adapter.get_coins(), g[0]) for g in growths[:buy_count]]
    for coin in buy_coins:
        if coin in sell:
            if adapter.can_sell(coin):
                log.info("Already owning %s %s of %s" % (owned_coins[coin], adapter.mode, coin))
                log.info("Prevented sell and rebuy")
                sell.remove(coin)
                buy_coins.remove(coin)
    sell_worth = sum([owned_coins[s] for s in sell])
    available_funds = sell_worth + adapter.get_funds()
    for coin in buy_coins:
        spend[coin] = available_funds / buy_count
    # remove buys when total would be under threshold
    for coin in list(spend.keys()):
        if spend[coin] < adapter.get_min_spend():
            spend.pop(coin, None)
    return (sell, spend)


def __stagnation_detection__(subreddit):
    """
    Is the price for the coin belonging to subreddit stagnating?
    """
    start_time = datetime.datetime.utcnow() - datetime.timedelta(hours=STAGNATION_HOURS)
    end_time = datetime.datetime.utcnow()
    price_data = db.get_all_price_data_in_interval(start_time, end_time)
    price_now = 0
    price_xhrs_ago = 0
    for line in price_data:
        if line[0] == subreddit:
            price_now = line[1]
            break
    for line in reversed(price_data):
        if line[0] == subreddit:
            price_xhrs_ago = line[1]
            break
    if price_now == 0 or price_xhrs_ago == 0:
        log.warn("No price data for %s. Assuming no stagnation." % (subreddit))
        return False
    price_change = (price_now - price_xhrs_ago) / price_xhrs_ago
    if price_change < STAGNATION_THRESHOLD:
        return True
    return False

def subreddit_growth_policy(adapter):
    now = datetime.datetime.utcnow()
    last_trade = adapter.get_last_trade_date()
    start_time = now - datetime.timedelta(hours=GROWTH_HOURS)
    subs = [coin[-1] for coin in adapter.get_coins()]
    growths = query.average_growth(db, subs, start_time, now, sort=True)
    growths.reverse()
    sell, spend = __sell_and_spendings__(adapter, growths[:K])
    log.info("Selling: %s" % (sell))
    log.info("Buying: %s" % (list(spend.keys())))
    for coin in sell:
        adapter.sell_all(coin)
    for coin, amount in spend.items():
        adapter.buy_by_symbol(coin, amount)
