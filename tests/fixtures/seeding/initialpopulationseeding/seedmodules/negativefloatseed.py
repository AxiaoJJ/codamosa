#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import tests.fixtures.seeding.initialpopulationseeding.dummycontainer as module0


def seed_test_case_0():
    var0 = -1.1
    var1 = -1.1
    var2 = module0.i_take_floats(var0, var1)
    assert var2 == "Floats are equal!"
