import tests.fixtures.seeding.initialpopulationseeding.dummycontainer as module0


def seed_test_case():
    var0 = "First"
    var1 = "Second"
    var2 = module0.i_take_strings(var0, var1)
    assert var2 == "Strings are different!"
