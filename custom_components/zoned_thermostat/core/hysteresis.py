"""Deterministic hysteresis evaluation for room heat demand."""

from typing import Any, Dict, Optional, Tuple


def calculate_heat_demand(
    current_temp: Optional[float],
    target_temp: float,
    hysteresis: float,
    previous_demand: bool,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Determine whether heat demand should be active using an asymmetric hysteresis band.

    Start Demand: current_temp <= (target_temp - hysteresis)
    Stop Demand:  current_temp >= (target_temp + hysteresis)
    Deadband:     (target_temp - hysteresis) < current_temp < (target_temp + hysteresis)
                  maintains the previous demand state to prevent chattering.

    Returns:
        (new_demand, reason, diagnostic_details)
    """
    if current_temp is None:
        return (
            False,
            "sensor_unavailable",
            {
                "current_temp": None,
                "target_temp": target_temp,
                "hysteresis": hysteresis,
                "previous_demand": previous_demand,
            },
        )

    # Round calculations to 2 decimal places to avoid floating point imprecision
    on_threshold = round(target_temp - hysteresis, 2)
    off_threshold = round(target_temp + hysteresis, 2)
    curr = round(current_temp, 2)

    details = {
        "current_temp": curr,
        "target_temp": target_temp,
        "hysteresis": hysteresis,
        "on_threshold": on_threshold,
        "off_threshold": off_threshold,
        "previous_demand": previous_demand,
    }

    if not previous_demand:
        if curr <= on_threshold:
            return (
                True,
                f"temperature_below_on_threshold: {curr}°C <= {on_threshold}°C",
                details,
            )
        return (
            False,
            f"temperature_above_on_threshold: {curr}°C > {on_threshold}°C",
            details,
        )

    # Previous demand was True
    if curr >= off_threshold:
        return (
            False,
            f"temperature_reached_off_threshold: {curr}°C >= {off_threshold}°C",
            details,
        )
    return (
        True,
        f"temperature_retaining_heat: {curr}°C < {off_threshold}°C",
        details,
    )
