import logging
import math

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, initial_balance=100.0, leverage_loss_cap=0.50, max_leverage=50):
        self.balance = initial_balance
        self.leverage_loss_cap = leverage_loss_cap
        self.max_leverage = max_leverage

    def calculate_position_size(self, current_balance):
        """Calculates margin based on tiered balance structure."""
        if current_balance <= 20000:
            rate = 0.10
        elif current_balance <= 40000:
            rate = 0.09
        elif current_balance <= 60000:
            rate = 0.08
        elif current_balance <= 80000:
            rate = 0.07
        elif current_balance <= 100000:
            rate = 0.06
        else:
            rate = 0.05
            
        return current_balance * rate

    def calculate_leverage(self, entry_price, sl_price, risk_scalar=1.0):
        """
        Calculates leverage such that if SL is hit, loss is ~50% of MARGIN.
        Includes a 10% Safety Buffer on the SL distance to account for slippage.
        risk_scalar: 1.0 for full risk, 0.5 for half risk, etc.
        """
        if entry_price == 0: return 1
        
        risk_pct = abs(entry_price - sl_price) / entry_price
        
        safe_risk_pct = risk_pct * 1.10 
        
        if safe_risk_pct == 0: return 1

        target_loss_cap = self.leverage_loss_cap * risk_scalar
        leverage = target_loss_cap / safe_risk_pct
        
        leverage = math.floor(leverage)
        return max(1, min(int(leverage), self.max_leverage))

    def determine_entry_action(self, signal_entry, current_market_price, explicit_order_type='MARKET'):
        """
        Determines if we should ENTER (Market/Limit) or ABORT.
        
        Logic:
        1. If explicit_order_type is 'LIMIT', ALWAYS return 'LIMIT'.
        2. If deviation <= 0.5%: Return 'MARKET' (Safe to enter).
        3. If deviation > 0.5% and <= 1.0%: Return 'LIMIT' (Try to catch pullback).
        4. If deviation > 1.0%: Return 'ABORT' (Too risky/late).
        
        Returns: (ACTION_STRING, price, reason)
        """
        if signal_entry == 0:
            return 'ABORT', 0, "Signal Entry is 0"

        if explicit_order_type == 'LIMIT':
            return 'LIMIT', signal_entry, "Explicit Limit Order requested"

        diff_percent = abs(signal_entry - current_market_price) / signal_entry

        if diff_percent <= 0.005: # 0.5%
            return 'MARKET', current_market_price, f"Price within 0.5% ({diff_percent*100:.2f}%)"
            
        elif diff_percent <= 0.010: # 1.0%
            return 'LIMIT', signal_entry, f"Price deviated {diff_percent*100:.2f}% (0.5-1.0%). Using Limit."
            
        else:
            return 'ABORT', 0, f"Price deviated {diff_percent*100:.2f}% (>1.0%). Too late."

    def scale_price(self, signal_price, market_price):
        """
        Re-scales signal price to match market price decimal formatting and magnitude.
        Example: Signal 0.00378, Market 0.00000378 -> Returns 0.00000378
        """
        if signal_price == 0 or market_price == 0:
            return signal_price

        signal_oom = math.floor(math.log10(signal_price))
        market_oom = math.floor(math.log10(market_price))
        
        diff_oom = signal_oom - market_oom
        
        if diff_oom != 0:
            scale_factor = 10 ** diff_oom
            logger.info(f"detected magnitude diff: {diff_oom}. Scaling...")
            
            # If signal is bigger (e.g. -3 vs -6, diff=3), we divide
            if diff_oom > 0:
                corrected_price = signal_price / (10 ** diff_oom)
            else:
                corrected_price = signal_price * (10 ** abs(diff_oom))

            # Double check within 10x range
            if not (market_price / 10 <= corrected_price <= market_price * 10):
                 # Fallback heuristic if simple log10 didn't land it close enough (e.g. 0.9 vs 0.0009)
                corrected_price = signal_price
                while corrected_price > market_price * 5:
                    corrected_price /= 10
                while corrected_price < market_price / 5:
                    corrected_price *= 10
            
            logger.info(f"Scaled price from {signal_price} to {corrected_price}")
            return corrected_price
            
        return signal_price
