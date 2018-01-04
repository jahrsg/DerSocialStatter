from AutoTrader.poloniex_adapter import Poloniex_Adapter
from AutoTrader import policies
import util

log = util.setup_logger(__name__)

class AutoTrader():
    def __init__(self, market):
        if market == "Poloniex":
            self.adapter = Poloniex_Adapter()
        else:
            log.warn("Invalid market {}.".format(market))

    def run(self):
        policies.subreddit_growth_policy(self.adapter)