import slapdash


@slapdash.refresh('counter', 0.2, 'counter_delay')
class RefreshExample:
    '''This model refreshes the `counter` attribute at a
    rate that is, by default, every 0.2 seconds, but can
    be changed by the additional attribute `counter_delay`.'''

    def __init__(self):
        self.counter_delay = 0.2
        self._counter = 0

    @property
    def counter(self) -> int:
        self._counter += 1
        return self._counter

if __name__ == '__main__':
    slapdash.run(RefreshExample())
