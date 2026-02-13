import logging
import math

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, initial_balance=100.0, leverage_loss_cap=0.50, max_leverage=50):
        self.balance = initial_balance
        self.leverage_loss_cap = leverage_loss_cap
        self.max_leverage = max_leverage

    def calculate_position_size(self, current_balance):
        """Calculates 10% margin of the LIVE compounding balance."""
        return current_balance * 0.10

    def calculate_leverage(self, entry_price, sl_price):
        """
        Calculates leverage such that hitting SL resulted in 70% loss of margin.
        Formula: Leverage = 0.70 / (% distance to SL)
        """
        if entry_price == 0:
            return 1
        
        distance_percent = abs(entry_price - sl_price) / entry_price
        
        if distance_percent == 0:
            return self.max_leverage

        raw_leverage = self.leverage_loss_cap / distance_percent
        leverage = min(int(raw_leverage), self.max_leverage)
        return max(1, leverage)

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

        # Explicit Override
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

        # Calculate magnitude difference (log10)
        # Use abs to handle potential negative logs safely (though price > 0)
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
