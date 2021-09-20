"""
WECOM3 HEADER
=============
see WE's sonicread.pdf

29 Bytes

"""

import struct

def data_block_header(open_file_object, size_header):  # size: n bytes
    if size_header == 29:
        # header is 29 bytes
        byte = open_file_object.read(29)
        # print(str(len(byte)))
        s = struct.Struct('<c B c L B B B B B B B B B B B B B B B B B B L')
        unpacked_data = s.unpack(byte)

        # contents of header according to sonic manual and Werner Eugster's sonicread.pdf
        header_file_type = unpacked_data[0]
        header_file_version = unpacked_data[1]
        header_anemometer_type_string = unpacked_data[2]

        header_serial_number = unpacked_data[3]
        header_average = unpacked_data[4]
        header_wind_report_mode = unpacked_data[5]

        header_string_format = unpacked_data[6]
        header_ascii_terminator = unpacked_data[7]
        header_echo = unpacked_data[8]

        header_message_mode = unpacked_data[9]
        header_confidence_tone = unpacked_data[10]
        header_axis_alignment = unpacked_data[11]

        header_speed_of_sound_mode = unpacked_data[12]
        header_absolute_temperature_mode = unpacked_data[13]
        header_analogue_inputs_enabled = unpacked_data[14:20]

        header_analogue_output_fsd = unpacked_data[20]
        header_direction_wrap_mode = unpacked_data[21]
        header_beginning = unpacked_data[22]

        # print("===================")
        # print("HEADER INFORMATION:")
        # print("===================")
        # print("HEADER SIZE: " + str(size_header))
        # print("---")
        # print("header_file_type: " + str(header_file_type))
        # print("header_file_version: " + str(header_file_version))
        # print("header_anemometer_type_string: " + str(header_anemometer_type_string))
        #
        # print("header_serial_number: " + str(header_serial_number))
        # print("header_average: " + str(header_average))
        # print("header_wind_report_mode: " + str(header_wind_report_mode))
        #
        # print("header_string_format: " + str(header_string_format))
        # print("header_ascii_terminator: " + str(header_ascii_terminator))
        # print("header_echo: " + str(header_echo))
        #
        # print("header_message_mode: " + str(header_message_mode))
        # print("header_confidence_tone: " + str(header_confidence_tone))
        # print("header_axis_alignment: " + str(header_axis_alignment))
        #
        # print("header_speed_of_sound_mode: " + str(header_speed_of_sound_mode))
        # print("header_absolute_temperature_mode: " + str(header_absolute_temperature_mode))
        # print("header_analogue_inputs_enabled: " + str(header_analogue_inputs_enabled))
        #
        # print("header_analogue_output_fsd: " + str(header_analogue_output_fsd))
        # print("header_direction_wrap_mode: " + str(header_direction_wrap_mode))
        # print("header_beginning: " + str(header_beginning))

        return None