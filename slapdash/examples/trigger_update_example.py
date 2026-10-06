import slapdash


class Sandwich:
    _peanut_butter: bool = False
    _jelly: bool = False

    @property
    @slapdash.trigger_update('tasty')
    def peanut_butter(self) -> bool:
        '''Do we have peanut butter on the sandwich?'''
        return self._peanut_butter

    @peanut_butter.setter
    def peanut_butter(self, value: bool):
        '''Put peanut butter on the sandwich.'''
        self._peanut_butter = value

    @property
    @slapdash.trigger_update('tasty')
    def jelly(self) -> bool:
        '''Do we have jelly on the sandwich?'''
        return self._jelly

    @jelly.setter
    def jelly(self, value: bool):
        '''Put jelly on the sandwich.'''
        self._jelly = value

    @property
    def tasty(self):
        return self._peanut_butter and self._jelly

if __name__ == '__main__':
    slapdash.run(Sandwich())
