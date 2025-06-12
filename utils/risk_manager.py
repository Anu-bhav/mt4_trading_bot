# utils/risk_manager.py
import math


def calculate_lot_size(
    account_balance: float,
    risk_percent: float,
    stop_loss_price_distance: float,
    value_per_point: float,
    min_lot: float,
    max_lot: float,
    lot_step: float,
) -> float:
    """
    Calculates and validates the lot size for a trade.

    :param value_per_point: The value of a full point movement for a 1.0 lot size trade.
    :param min_lot: The minimum allowed lot size from the broker.
    :param max_lot: The maximum allowed lot size from the broker.
    :param lot_step: The smallest increment lots can be changed by (e.g., 0.01 or 0.1).
    :return: The calculated and validated lot size.
    """
    if stop_loss_price_distance <= 0 or value_per_point <= 0:
        return 0.0  # Cannot calculate risk, return 0 to abort.

    # 1. Calculate the ideal, unconstrained lot size
    risk_amount = account_balance * (risk_percent / 100.0)
    stop_loss_value_per_lot = stop_loss_price_distance * value_per_point
    if stop_loss_value_per_lot <= 0:
        return 0.0

    lot_size = risk_amount / stop_loss_value_per_lot

    # 2. Apply broker constraints
    # Clamp the lot size to the broker's min/max limits
    lot_size = max(min_lot, min(lot_size, max_lot))

    # 3. Adjust for the lot step
    # This correctly rounds the lot size DOWN to the nearest valid step.
    # For example, if lot_step is 0.01 and lot_size is 0.039, it will become 0.03.
    # If lot_step is 0.1 and lot_size is 0.28, it will become 0.2.
    if lot_step > 0:
        lot_size = math.floor(lot_size / lot_step) * lot_step

    # Return the final, validated lot size, rounded for safety.
    return round(lot_size, 2)
