from slapdash import Model


class Simple:
    def __init__(self):
        self.A_int = 0
        self.B_float = 1.5
        self.C_bool = False
        self.D_str = 'test'


def test_simple():
    simple = Simple()
    model = Model(simple)

    assert simple.A_int == model['A_int']
    assert simple.B_float == model['B_float']
    assert simple.C_bool == model['C_bool']
    assert simple.D_str == model['D_str']

    model['A_int'] = 1
    model['B_float'] = 2.5
    model['C_bool'] = True
    model['D_str'] = '_=_'

    assert simple.A_int == 1
    assert simple.B_float == 2.5
    assert simple.C_bool is True
    assert simple.D_str == '_=_'

    simple.A_int = 2
    simple.B_float = 3.5
    simple.C_bool = False
    simple.D_str = '!!!'

    assert model['A_int'] == 2
    assert model['B_float'] == 3.5
    assert model['C_bool'] is False
    assert model['D_str'] == '!!!'


class Branch:
    def __init__(self):
        self.simple = Simple()


class Tree:
    def __init__(self):
        self.branch = Branch()
        self.simple = Simple()


def test_tier():
    tree = Tree()
    model = Model(tree)

    assert tree.simple.A_int == model['simple.A_int']
    assert tree.simple.B_float == model['simple.B_float']
    assert tree.simple.C_bool == model['simple.C_bool']
    assert tree.simple.D_str == model['simple.D_str']
    assert tree.branch.simple.A_int == model['branch.simple.A_int']
    assert tree.branch.simple.B_float == model['branch.simple.B_float']
    assert tree.branch.simple.C_bool == model['branch.simple.C_bool']
    assert tree.branch.simple.D_str == model['branch.simple.D_str']
    assert model.serialize(model['simple']) == {
        'A_int': 0, 'B_float': 1.5, 'C_bool': False, 'D_str': 'test'}

    tree.simple.A_int = 10
    tree.simple.B_float = 11.1
    tree.simple.C_bool = False
    tree.simple.D_str = '$$$$'
    tree.branch.simple.A_int = 12
    tree.branch.simple.B_float = 13.2
    tree.branch.simple.C_bool = True
    tree.branch.simple.D_str = '&&&&&'

    assert model['simple.A_int'] == 10
    assert model['simple.B_float'] == 11.1
    assert model['simple.C_bool'] is False
    assert model['simple.D_str'] == '$$$$'
    assert model['branch.simple.A_int'] == 12
    assert model['branch.simple.B_float'] == 13.2
    assert model['branch.simple.C_bool'] is True
    assert model['branch.simple.D_str'] == '&&&&&'
    assert model.serialize(model['simple']) == {
        'A_int': 10, 'B_float': 11.1, 'C_bool': False, 'D_str': '$$$$'}

    model['simple.A_int'] = 14
    model['simple.B_float'] = 15.3
    model['simple.C_bool'] = True
    model['simple.D_str'] = 'abab'
    model['branch.simple.A_int'] = 16
    model['branch.simple.B_float'] = 17.4
    model['branch.simple.C_bool'] = False
    model['branch.simple.D_str'] = 'test'

    assert tree.simple.A_int == 14
    assert tree.simple.B_float == 15.3
    assert tree.simple.C_bool is True
    assert tree.simple.D_str == 'abab'
    assert tree.branch.simple.A_int == 16
    assert tree.branch.simple.B_float == 17.4
    assert tree.branch.simple.C_bool is False
    assert tree.branch.simple.D_str == 'test'
    assert model.serialize(model['simple']) == {
        'A_int': 14, 'B_float': 15.3, 'C_bool': True, 'D_str': 'abab'}


class SimpleArray:
    def __init__(self):
        self.array_int = [1, 2, 3, 4]
        self.array_float = [0.1, 0.2, 0.3]
        self.array_bool = [False, False]
        self.array_str = ['this', 'is', 'a', 'test']
        self.array_mix = [0, 0.1, False, 'test']


def test_array():
    simple_array = SimpleArray()
    model = Model(simple_array)

    assert simple_array.array_int == model['array_int'].serialize()
    assert simple_array.array_float == model['array_float'].serialize()
    assert simple_array.array_bool == model['array_bool'].serialize()
    assert simple_array.array_str == model['array_str'].serialize()
    assert simple_array.array_mix == model['array_mix'].serialize()

    model['array_int'][0] = 9
    model['array_float'][2] = 2.5
    model['array_bool'][1] = True
    model['array_str'][3] = '@@@@'
    model['array_mix'][2] = 0

    assert simple_array.array_int[0] == 9
    assert simple_array.array_float[2] == 2.5
    assert simple_array.array_bool[1] is True
    assert simple_array.array_str[3] == '@@@@'
    assert simple_array.array_mix[2] == 0

    simple_array.array_int[2] = 11
    simple_array.array_float[1] = 3.7
    simple_array.array_bool[0] = True
    simple_array.array_str[1] = '###'
    simple_array.array_mix[3] = True

    assert model['array_int'][2] == 11
    assert model['array_float'][1] == 3.7
    assert model['array_bool'][0] is True
    assert model['array_str'][1] == '###'
    assert model['array_mix'][3] is True


class Subclass:
    subclass_array1d_permanent = [7., 8., 9.]
    subclass_array2d_permanent = [[7., 8., 9.], [7., 8., 9.]]

    def __init__(self):
        self.subclass_array1d_on_init = [4., 5., 6.]
        self.subclass_array2d_on_init = [[4., 5., 6.], [4., 5., 6.]]

class HeavilyNested:
    array1d_permanent = [1.5, 2.5, 3.5]
    array2d_permanent = [[1.6, 2.6, 3.6], [1.6, 2.6, 3.6]]

    _array3d1 = [[[1.1, 2.1],],]
    array3d2 = [[[1.11, 2.11],],]

    subclass_permanent = Subclass()
    list_of_subclasses = [Subclass(), Subclass(), Subclass()]

    def __init__(self):
        self.array1d_on_init = [1.7, 2.7, 3.7] # unsettable
        self.array2d_on_init = [[1.8, 2.8, 3.8], [1.8, 2.8, 3.8]] # unsettable
        self.subclass_on_init = Subclass()

    @property
    def array3d1(self):
        return self._array3d1

    @array3d1.setter
    def array3d1(self, value):
        self._array3d1 = value


def test_nesting():
    nested_array = HeavilyNested()
    model = Model(nested_array)

    assert nested_array.array1d_permanent == model['array1d_permanent'].serialize()
    assert nested_array.array2d_permanent == model['array2d_permanent'].serialize()
    assert nested_array.array3d1 == model['array3d1'].serialize()
    assert nested_array.array3d2 == model['array3d2'].serialize()
    assert nested_array.subclass_permanent.subclass_array1d_permanent == model['subclass_permanent.subclass_array1d_permanent'].serialize()
    assert nested_array.subclass_permanent.subclass_array2d_permanent == model['subclass_permanent.subclass_array2d_permanent'].serialize()

    assert nested_array.array2d_permanent[0] == model['array2d_permanent[0]'].serialize()
    assert nested_array.array3d1[0][0] == model['array3d1[0][0]'].serialize()
    assert nested_array.array3d2[0][0] == model['array3d2[0][0]'].serialize()
    assert nested_array.subclass_permanent.subclass_array2d_permanent[0] == model['subclass_permanent.subclass_array2d_permanent[0]'].serialize()

    assert nested_array.array2d_permanent[0] == model['array2d_permanent'].serialize()[0]
    assert nested_array.array3d1[0][0] == model['array3d1'].serialize()[0][0]
    assert nested_array.array3d2[0][0] == model['array3d2'].serialize()[0][0]
    assert nested_array.subclass_permanent.subclass_array2d_permanent[0] == model['subclass_permanent.subclass_array2d_permanent'].serialize()[0]

    model['array1d_permanent'][0] = 0.01
    model['array2d_permanent'][0][1] = 0.02
    model['array3d1'][0][0][0] = 0.03
    model['array3d2'][0][0][1] = 0.04
    model['subclass_permanent.subclass_array1d_permanent'][1] = 0.05
    model['subclass_permanent.subclass_array2d_permanent'][0][2] = 0.06

    assert nested_array.array1d_permanent[0] == 0.01
    assert nested_array.array2d_permanent[0][1] == 0.02
    assert nested_array.array3d1[0][0][0] == 0.03
    assert nested_array.array3d2[0][0][1] == 0.04
    assert nested_array.subclass_permanent.subclass_array1d_permanent[1] == 0.05
    assert nested_array.subclass_permanent.subclass_array2d_permanent[0][2] == 0.06
