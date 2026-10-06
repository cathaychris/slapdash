#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Created: 01/2022
# Author: Carmelo Mordini <cmordini@phys.ethz.ch>

import slapdash
from enum import Enum


class Color(Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'


class DisplayType(Enum):
    CURRENT = "display current"
    POWER = "display power"


class ColorfulDashboard:
    '''This model demonstrates the enumerator data type,
    which will appear as a drop-down box in the interface
    from which you can select an option. The value passed
    to the server is the string value of the enumerator, not the
    Pythonic keyword.'''

    color = Color.GREEN
    _display = DisplayType.CURRENT

    @property
    def display_type(self):
        print("getting display type")
        return self._display

    @display_type.setter
    def display_type(self, value):
        print("setting display type")
        self._display = value


if __name__ == '__main__':
    slapdash.run(ColorfulDashboard(), port=8002)
