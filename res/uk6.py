"""
pgoapi - Pokemon Go API
Copyright (c) 2016 tjado <https://github.com/tejado>
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
OR OTHER DEALINGS IN THE SOFTWARE.
Author: tjado <https://github.com/tejado>
"""

import xxhash
import struct
import os
import ctypes
import six

static_seed = 0x1B845238


def d2h(f):
    if not f:
        return '\x00\x00\x00\x00\x00\x00\x00\x00'
    hex_str = hex(struct.unpack('<Q', struct.pack('<d', f))[0])[2:].replace('L','')
    if len(hex_str) % 2:
        hex_str = '0' + hex_str
    return hex_str.decode('hex')


def generateLocation1(authticket, lat, lng, alt):
    firstHash = xxhash.xxh32(authticket, seed=static_seed).intdigest()
    locationBytes = d2h(lat) + d2h(lng) + d2h(alt)
    return xxhash.xxh32(locationBytes, seed=firstHash).intdigest()


def generateLocation2(lat, lng, alt):
    locationBytes = d2h(lat) + d2h(lng) + d2h(alt)
    return xxhash.xxh32(locationBytes, seed=static_seed).intdigest()


def generateRequestHash(authticket, request):
    firstHash = xxhash.xxh64(authticket, seed=static_seed).intdigest()
    return ctypes.c_longlong(xxhash.xxh64(request, seed=firstHash).intdigest()).value


def generate_signature(signature_plain, signature_lib):
    iv = os.urandom(32)

    output_size = ctypes.c_size_t()

    signature_lib.encrypt(signature_plain, len(signature_plain), iv, 32, None, ctypes.byref(output_size))
    output = (ctypes.c_ubyte * output_size.value)()
    signature_lib.encrypt(signature_plain, len(signature_plain), iv, 32, ctypes.byref(output), ctypes.byref(output_size))
    signature = b''.join(list(map(lambda x: six.int2byte(x), output)))
    return signature
