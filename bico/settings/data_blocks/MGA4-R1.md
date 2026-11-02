# MGA4-R1

Multi-gas analyzer for four gases, from MIRO.

## Variables

VAR#1: CO2_DRY ... CO2 dry mole fraction (in dry air), mixing ratio, ppm (parts per million) (umol mol-1)
VAR#2: H2O ... water vapour mole fraction (in wet air) (mmol mol-1)
VAR#3: N2O_DRY ... N2O dry mole fraction (in dry air) (nmol mol-1)
VAR#4: COS_DRY ... COS dry mole fraction (in dry air) (nmol mol-1)
VAR#5: T_CELL ... cell temperature (deg C)
VAR#6: P_CELL ... cell pressure (Pa)
VAR#7: MIRO_STATUS_CODE ... status code from MIRO (needs description)
VAR#8: VALVES ... auxiliary variable logged as part of the ABACOS project
VAR#9: VALVES_ONLINE ... auxiliary variable logged as part of the ABACOS project
VAR#10: INPUTS ... auxiliary variable logged as part of the ABACOS project
VAR#11: INPUTS_ONLINE ... auxiliary variable logged as part of the ABACOS project
VAR#12: FLOW_VOLRATE_MGA_EC ... auxiliary variable logged as part of the ABACOS project (l min-1)
VAR#13: FLOW_VOLRATE_MGA_LF ... auxiliary variable logged as part of the ABACOS project (l min-1)
VAR#14: P_TANK_ZERO ... auxiliary variable logged as part of the ABACOS project (kPa)
VAR#15: P_TANK_SPAN ... auxiliary variable logged as part of the ABACOS project (kPa)
VAR#16: ABACOS_STATUS_CODE ... auxiliary variable logged as part of the ABACOS project

## BICO Settings

- This datablock does not need conversion because it is already logged in ASCII format.

## Details

- Data from the MIRO laser that measures also COS.
- Datablock originates from the logging script `rECord`.
