import slapdash


class HelloWorld:
    '''This model has a single string attribute,
    and should display this in a textbox in the interface.
    It can be changed by the user.'''

    message = 'Hello! I am a slapdash dashboard.'


if __name__ == '__main__':
    slapdash.run(HelloWorld())
