"""
A pure-Python shim to replace the missing 'crc16' package.
Implements the crc16xmodem function expected by pytonlib/tonsdk.
"""
CRC16_XMODEM_TABLE = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
    # ... (include the full table; the complete list is available in the search results[citation:7])
    0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
    0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
    0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
]

def crc16xmodem(data, crc=0x0000):
    """Calculate CRC-16/XMODEM checksum."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    for byte in data:
        crc = ((crc << 8) & 0xFFFF) ^ CRC16_XMODEM_TABLE[((crc >> 8) ^ byte) & 0xFF]
    return crc
