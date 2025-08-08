"""
Utility functions for calculating FIT target values based on reverse-engineered formula
"""

def calculate_fit_targets(power_low_fraction, power_high_fraction=None):
    """
    Calculate target_low and target_high values for FIT files using reverse-engineered formula.
    
    The formula was reverse-engineered from analyzing the correctly encoded pacing1.fit file:
    - Base value: 1000 (constant offset)
    - Power scaling: 280 (multiplier for power fraction)
    - Range scaling: ~56 (determines target range width)
    
    Args:
        power_low_fraction: Power as fraction of FTP (e.g., 0.5 for 50% FTP)
        power_high_fraction: Optional high power fraction for ranges (e.g., warmup/cooldown)
    
    Returns:
        tuple: (target_low, target_high) - integer values for FIT file
    
    Examples:
        calculate_fit_targets(0.5)      -> (1126, 1154)  # 50% FTP steady
        calculate_fit_targets(0.75)     -> (1189, 1231)  # 75% FTP 
        calculate_fit_targets(0.5, 0.75) -> (1140, 1210)  # 50-75% warmup range
    """
    
    if power_high_fraction is None:
        power_high_fraction = power_low_fraction
    
    # Reverse-engineered formula constants from pacing1.fit analysis
    BASE_VALUE = 1000
    POWER_SCALE = 280  
    RANGE_SCALE = 56
    
    if power_low_fraction == power_high_fraction:
        # Single power value (steady state, intervals)
        midpoint = BASE_VALUE + POWER_SCALE * power_low_fraction
        half_range = int(RANGE_SCALE * power_low_fraction / 2)
        target_low = int(midpoint - half_range)
        target_high = int(midpoint + half_range)
    else:
        # Power range (warmup, cooldown)
        # Calculate endpoints separately for better accuracy
        low_midpoint = BASE_VALUE + POWER_SCALE * power_low_fraction
        low_half_range = int(RANGE_SCALE * power_low_fraction / 2)
        target_low = int(low_midpoint - low_half_range)
        
        high_midpoint = BASE_VALUE + POWER_SCALE * power_high_fraction  
        high_half_range = int(RANGE_SCALE * power_high_fraction / 2)
        target_high = int(high_midpoint + high_half_range)
    
    return target_low, target_high