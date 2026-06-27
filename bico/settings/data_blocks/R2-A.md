# R2-A

## Variables
- U ...  First horizontal wind component (x)
- V ...  Second horizontal wind component (y)
- W ...  Vertical wind component (z)
- T_SONIC ... Sonic temperature
  Note that this variable has ```'conversion_type': 'exception'```, because a special conversion
  is needed to convert from binary to proper units. See Details below for conversion steps.

## BICO Settings
- For an explanation of the different variable property settings, please see ```_help_bico_settings.md```.

*Before BICO, the binary conversion was done in FCT FluxCalcTool:*
- Old ID in FCT: r2_1_without_extrabyte
- Old data block in FCT: data_block_sonic_r2_1_without_extrabyte
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

## Details
- Regarding T_SONIC --> C code from ethconvert:  
  ```if(is_R2_sonic){c=0.02*dataWECOM3.Tv; Tv=c*c/403.0-273.15;	/* Tv in degrees C */```  
  In BICO, the conversion is done in module ```bin_conversion_exceptions.py```.


## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters
