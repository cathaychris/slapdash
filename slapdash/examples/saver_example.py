from pathlib import Path

import slapdash
from slapdash import Saver


class Ammo:
    bombs: int = 0
    miniguns: int = 0


@Saver(Path(__file__).parent / 'settings.json')  # settings are loaded when decorator is read
class Interface:
    '''This model demonstrates the effect of the `Saver` decorator,
    which means that attributes present in the `settings.json`
    schema will be loaded into the dashboard when it first runs, and saved
    back into the JSON file whenever they are changed.'''

    ammo = Ammo()
    missiles: int = 0

    def launch_missiles(self):
        if self.missiles:
            print(f"You have {self.missiles} missiles, God bless America")
        else:
            print("No missiles in the arsenal")


if __name__ == "__main__":

    interface = Interface()
    interface.launch_missiles()  # anything run after settings are applied goes here
    slapdash.run(interface)
