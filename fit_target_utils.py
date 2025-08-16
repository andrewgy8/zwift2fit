"""
Utility functions for calculating FIT target values based on reverse-engineered formula
"""
def calculate_ftp_targets(power_low_fraction, ftp, power_high_fraction=None):
    """
    Calculate target_low and target_high values for FIT files using reverse-engineered formula.
    
    The formula was reverse-engineered from analyzing pacing1.fit, which was created with FTP=280.
    The FIT format stores actual power values, not normalized percentages, so we need the FTP
    to calculate the correct targets.
    
    Reverse-engineered formula: 
        midpoint = 1000 + ftp * power_fraction
        range = 0.2 * ftp * power_fraction  (approximately)
        target_low = midpoint - range/2
        target_high = midpoint + range/2
    
    Args:
        power_low_fraction: Power as fraction of FTP (e.g., 0.5 for 50% FTP)
        power_high_fraction: Optional high power fraction for ranges (e.g., warmup/cooldown)
        ftp: Functional Threshold Power in watts (required)
    
    Returns:
        tuple: (target_low, target_high) - integer values for FIT file
    
    Examples:
        calculate_fit_targets(0.5, ftp=280)        -> (1126, 1154)  # 50% of 280W FTP
        calculate_fit_targets(0.5, ftp=250)        -> (1097, 1123)  # 50% of 250W FTP
        calculate_fit_targets(0.5, 0.75, ftp=280)  -> (1126, 1231)  # 50-75% range
    """
    
    if ftp is None:
        raise ValueError("FTP must be provided to calculate FIT target values")
    
    if power_high_fraction is None:
        power_high_fraction = power_low_fraction
    
    if power_low_fraction == power_high_fraction:
        # Single power value (steady state, intervals)
        midpoint = 1000 + ftp * power_low_fraction
        half_range = int(0.2 * ftp * power_low_fraction / 2)
        target_low = int(midpoint - half_range)
        target_high = int(midpoint + half_range)
    else:
        # Power range (warmup, cooldown)  
        # Calculate endpoints separately for better accuracy
        low_midpoint = 1000 + ftp * power_low_fraction
        low_half_range = int(0.2 * ftp * power_low_fraction / 2)
        target_low = int(low_midpoint - low_half_range)
        
        high_midpoint = 1000 + ftp * power_high_fraction
        high_half_range = int(0.2 * ftp * power_high_fraction / 2)
        target_high = int(high_midpoint + high_half_range)
    
    return target_low, target_high