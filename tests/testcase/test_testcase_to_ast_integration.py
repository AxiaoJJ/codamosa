#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from ast import Module

import astor
import pytest

import pynguin.assertion.assertion as ass
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt
import pynguin.testcase.testcase_to_ast as tc_to_ast


@pytest.fixture()
def simple_test_case(constructor_mock):
    test_case = dtc.DefaultTestCase()
    int_stmt = stmt.IntPrimitiveStatement(test_case, 5)
    constructor_stmt = stmt.ConstructorStatement(
        test_case, constructor_mock, {"y": int_stmt.ret_val}
    )
    constructor_stmt.add_assertion(ass.ObjectAssertion(constructor_stmt.ret_val, 3))
    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_stmt)
    return test_case


def test_test_case_to_ast_once(simple_test_case):
    visitor = tc_to_ast.TestCaseToAstVisitor()
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert (
        astor.to_source(Module(body=visitor.test_case_asts[0]))
        == "int_0 = 5\nsome_type_0 = module_0.SomeType(int_0)\nassert some_type_0 == 3\n"
    )


def test_test_case_to_ast_twice(simple_test_case):
    visitor = tc_to_ast.TestCaseToAstVisitor()
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert (
        astor.to_source(Module(body=visitor.test_case_asts[0]))
        == "int_0 = 5\nsome_type_0 = module_0.SomeType(int_0)\nassert some_type_0 == 3\n"
    )
    assert (
        astor.to_source(Module(body=visitor.test_case_asts[1]))
        == "int_0 = 5\nsome_type_0 = module_0.SomeType(int_0)\nassert some_type_0 == 3\n"
    )


def test_test_case_to_ast_module_aliases(simple_test_case):
    visitor = tc_to_ast.TestCaseToAstVisitor()
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert dict(visitor.module_aliases) == {
        "tests.fixtures.accessibles.accessible": "module_0"
    }
