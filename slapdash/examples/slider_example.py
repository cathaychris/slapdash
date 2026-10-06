#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Created: 04/2022
# Author: Philip Leindecker <pleindecker@student.ethz.ch>

import slapdash
from slapdash import metadata, refresh
import random

class SliderSubclass:
    _metadata = {
        'float_prop': {'min': 0, 'max': 10, 'step': 0.01, 'units': 'V', 'renderAs': 'slider'},
    }

    _float_prop: float = 5.0

    @property
    def float_prop(self) -> float:
        return self._float_prop

    @float_prop.setter
    def float_prop(self, value: float):
        self._float_prop = value

@refresh('readonly_slider', 1.)
class SliderDashboard:
    number: float = 111.0
    _float_prop: float = 5.0
    _another_prop: float = 4.0
    _int_prop: int = 1
    _free_prop: float = 3.0
    slide_values = [1., 2., 3.]

    _metadata = {
        'float_prop': {'min': 0, 'max': 10, 'step': 0.01, 'units': 'V', 'renderAs': 'slider'},
        'free_prop': {'renderAs': 'slider'},
        'slide_values': {'min': 0, 'max': 10, 'step': 0.01, 'units': 'megatons', 'renderAs': 'slider'},
        'number': {'units': 'person-months'},
        'readonly_slider': {'min': 2, 'max': 44, 'step': 1, 'units': 'ion traps in a car', 'renderAs': 'slider'},
        'ro_slider': {'min': 2, 'max': 44, 'step': 1, 'units': 'broken wafers', 'renderAs': 'slider'},
    }

    def __init__(self):
        self.subclass = SliderSubclass()

    @property
    def float_prop(self) -> float:
        return self._float_prop

    @float_prop.setter
    def float_prop(self, value: float):
        self._float_prop = value

    # You can specify metadata locally, as well:
    @metadata({'min': 0, 'max': 10, 'step': 0.01, 'units': 'km', 'renderAs': 'slider'})
    @property
    def another_prop(self) -> float:
        return self._another_prop

    @another_prop.setter
    def another_prop(self, value: float):
        self._another_prop = value

    # Also for integers:
    @metadata({'min': 0, 'max': 10, 'step': 1, 'units': 'Russian warship(s)', 'renderAs': 'slider'})
    @property
    def int_prop(self) -> int:
        return self._int_prop

    @int_prop.setter
    def int_prop(self, value: int):
        self._int_prop = value

    # No metadata specified? Defaults are 0 to 100 in steps of 1:
    @property
    def free_prop(self) -> float:
        return self._free_prop

    @free_prop.setter
    def free_prop(self, value: float):
        self._free_prop = value

    # does not get set as "disabled"!
    @property
    def readonly_slider(self) -> int:
        return random.randrange(2, 44, 1)

    @property
    def ro_slider(self) -> int:
        return 3

    def up_free_prop(self):
        self.free_prop += 1.

    def down_free_prop(self):
        self.free_prop -= 1.


if __name__ == '__main__':
    slapdash.run(SliderDashboard(), port=8000)

    # Run with: python -m slapdash.examples slider_example
    # Open in Browser: http://localhost:8000
