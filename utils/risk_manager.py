# utils/risk_manager.py
import math


def calculate_lot_size(
    account_balance: float, risk_percent: float, stop_loss_price_distance: float, value_per_point: float
) -> float:
    """
    Calculates lot size based on a fixed fractional risk model using price distance.

    :param account_balance: The current equity or balance of the account.
    :param risk_percent: The percentage of the account to risk (e.g., 1.0 for 1%).
    :param stop_loss_price_distance: The absolute price distance to the stop loss (e.g., 0.00250).
    :param value_per_point: The value of a full point movement for a 1.0 lot size trade (e.g., tick_value * 10^digits).
    :return: The calculated lot size, rounded down to 2 decimal places.
    """
    if stop_loss_price_distance <= 0 or value_per_point <= 0:
        print("[RiskManager] ERROR: Stop loss distance and value per point must be positive.")
        return 0.01  # Fallback to minimum lot size

    # 1. Calculate the risk amount in the account currency (e.g., USD)
    risk_amount = account_balance * (risk_percent / 100.0)

    # 2. Calculate the value of the stop loss in currency for a 1.0 lot trade
    stop_loss_value_per_lot = stop_loss_price_distance * value_per_point

    # 3. Calculate the required lot size
    if stop_loss_value_per_lot <= 0:
        print("[RiskManager] ERROR: Stop loss value per lot is zero or negative. Cannot calculate lot size.")
        return 0.01

    lot_size = risk_amount / stop_loss_value_per_lot

    # Floor to 2 decimal places to be safe.
    return math.floor(lot_size * 100) / 100.0
