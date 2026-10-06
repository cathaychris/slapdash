#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Created: 01/2022
# Author: Carmelo Mordini <cmordini@phys.ethz.ch>

'''
Define base types
'''

READONLY = 'readonly'

BASE_TYPES = {
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
    'enum': str,  # enums are serialized by their str(value)
}
