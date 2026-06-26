def dblock_r2a_t_sonic(var_val):
    """Special conversion for T_SONIC in R2-A"""
    var_val *= 0.02
    var_val *= var_val
    var_val /= 403
    var_val -= 273.15  # To °C
    return var_val
