# utils/risk_manager.py
import math


# --- THIS IS THE CORRECTED FUNCTION SIGNATURE AND USAGE ---
def calculate_lot_size(
    account_balance: float,
    risk_percent: float,
    stop_loss_price_distance: float,
    value_per_point: float,
    lot_min: float,
    lot_max: float,
    lot_step: float,
) -> float:
    """
    Calculates and validates the lot size for a trade.
    """
    if stop_loss_price_distance <= 0 or value_per_point <= 0:
        return 0.0

    risk_amount = account_balance * (risk_percent / 100.0)
    stop_loss_value_per_lot = stop_loss_price_distance * value_per_point
    if stop_loss_value_per_lot <= 0:
        return 0.0

    lot_size = risk_amount / stop_loss_value_per_lot

    # Clamp the lot size to the broker's min/max limits
    # The variable name is now correct.
    lot_size = max(lot_min, min(lot_size, lot_max))

    # Adjust for the lot step
    if lot_step > 0:
        lot_size = math.floor(lot_size / lot_step) * lot_step

    return round(lot_size, 2)
