# BICO Settings

## Variable Properties
- 'order' ... Order in the data block variable sequence
- 'bytes' ... Number of bytes in the binary data
- 'format' ... Format to convert from binary to integers, floats, etc.
- 'gain_on_signal' ... Gain that was applied to the raw data signal, to get to units *divide* by this gain
- 'offset_on_signal' ... Offset that was added to the raw data signal, to get to units *subtract* this offset
- 'apply_gain' ... Gain that is applied during conversion, e.g. to convert to different units if needed
- 'add_offset' ... Offset that is added during conversion, e.g. to convert to different units if needed
- 'units' ... Units
- 'conversion' ... Information for BICO if the conversion should be done using the provided gain and
  offset settings, or if a special conversion is needed to yield proper values.
  There are the following options:
  - 'regular': default conversion, BICO uses the gain and offset info to convert to desired values
  - 'exception': non-default conversion, in this case BICO uses the info provided in 'datablock' in
    combination with the variable name and applies the respective conversion defined in the file
    ```bin_converion_exceptions.py```.
  - For example: T_SONIC in datablock R2-A needs a special conversion. For this variable, BICO detects
    that ```'conversion' == 'exception'``` and therefore searches for the exception conversion for
    variable ```T_SONIC``` for datablock ```R2-A``` in the file ```bin_converion_exceptions.py```.
- 'datablock' ... Data block ID
