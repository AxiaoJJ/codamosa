#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides the MOSA test-generation strategy."""
import logging
from typing import List, Set

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.testcasechromosome as tcc
from pynguin.ga.comparators.dominancecomparator import DominanceComparator
from pynguin.ga.operators.ranking.crowdingdistance import (
    fast_epsilon_dominance_assignment,
)
from pynguin.generation.algorithms.archive import Archive
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.generation.algorithms.wraptestsuitemixin import WrapTestSuiteMixin
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.statistics.statistics import RuntimeVariable, StatisticsTracker


# pylint: disable=too-many-instance-attributes
class MOSATestStrategy(TestGenerationStrategy, WrapTestSuiteMixin):
    """Implements the Many-Objective Sorting Algorithm MOSA."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        super().__init__()
        self._archive: Archive[ff.FitnessFunction, tcc.TestCaseChromosome]
        self._population: List[tcc.TestCaseChromosome] = []
        self._current_iteration = 0
        self._number_of_goals = -1

    def generate_tests(self) -> chrom.Chromosome:
        self._logger.info("Start generating tests")
        self._archive = Archive(set(self._fitness_functions))
        self._number_of_goals = len(self._fitness_functions)

        self._current_iteration = 0
        self._population = self._get_random_population()
        self._archive.update(self._population)

        # Calculate dominance ranks and crowding distance
        fronts = self._ranking_function.compute_ranking_assignment(
            self._population, self._archive.uncovered_goals
        )
        for i in range(fronts.get_number_of_sub_fronts()):
            fast_epsilon_dominance_assignment(
                fronts.get_sub_front(i), self._archive.uncovered_goals
            )

        while (
            not self._stopping_condition.is_fulfilled()
            and self._number_of_goals - len(self._archive.covered_goals) != 0
        ):
            self.evolve()
            self._notify_iteration()
            self._current_iteration += 1

        StatisticsTracker().track_output_variable(
            RuntimeVariable.AlgorithmIterations, self._current_iteration
        )
        return self.create_test_suite(
            self._archive.solutions
            if len(self._archive.solutions) > 0
            else self._get_best_individuals()
        )

    def evolve(self) -> None:
        """Runs one evolution step."""
        offspring_population: List[
            tcc.TestCaseChromosome
        ] = self._breed_next_generation()

        # Create union of parents and offspring
        union: List[tcc.TestCaseChromosome] = []
        union.extend(self._population)
        union.extend(offspring_population)

        uncovered_goals: Set[ff.FitnessFunction] = self._archive.uncovered_goals

        # Ranking the union
        self._logger.debug("Union Size = %d", len(union))
        # Ranking the union using the best rank algorithm
        fronts = self._ranking_function.compute_ranking_assignment(
            union, uncovered_goals
        )

        remain = len(self._population)
        index = 0
        self._population.clear()

        # Obtain the next front
        front = fronts.get_sub_front(index)

        while remain > 0 and remain >= len(front) != 0:
            # Assign crowding distance to individuals
            fast_epsilon_dominance_assignment(front, uncovered_goals)
            # Add the individuals of this front
            self._population.extend(front)
            # Decrement remain
            remain -= len(front)
            # Obtain the next front
            index += 1
            if remain > 0:
                front = fronts.get_sub_front(index)

        # Remain is less than len(front[index]), insert only the best one
        if remain > 0 and len(front) != 0:
            fast_epsilon_dominance_assignment(front, uncovered_goals)
            front.sort(key=lambda t: t.distance, reverse=True)
            for k in range(remain):
                self._population.append(front[k])

        self._archive.update(self._population)

    def _get_random_population(self) -> List[tcc.TestCaseChromosome]:
        population: List[tcc.TestCaseChromosome] = []
        for _ in range(config.INSTANCE.population):
            chromosome = self._chromosome_factory.get_chromosome()
            for fitness_function in self._fitness_functions:
                chromosome.add_fitness_function(fitness_function)
            population.append(chromosome)
        return population

    def _breed_next_generation(self) -> List[tcc.TestCaseChromosome]:
        offspring_population: List[tcc.TestCaseChromosome] = []
        for _ in range(int(config.INSTANCE.population / 2)):
            parent_1 = self._selection_function.select(self._population)[0]
            parent_2 = self._selection_function.select(self._population)[0]
            offspring_1 = parent_1.clone()
            offspring_2 = parent_2.clone()

            # Apply crossover
            if randomness.next_float() <= config.INSTANCE.crossover_rate:
                try:
                    self._crossover_function.cross_over(offspring_1, offspring_2)
                except ConstructionFailedException:
                    self._logger.debug("CrossOver failed.")
                    continue

            # Apply mutation on offspring_1
            self._mutate(offspring_1)
            if offspring_1.has_changed():
                offspring_population.append(offspring_1)

            # Apply mutation on offspring_2
            self._mutate(offspring_2)
            if offspring_2.has_changed():
                offspring_population.append(offspring_2)

        # Add new randomly generated tests
        for _ in range(
            int(config.INSTANCE.population * config.INSTANCE.test_insertion_probability)
        ):
            if len(self._archive.covered_goals) == 0 or randomness.next_bool():
                tch: tcc.TestCaseChromosome = self._chromosome_factory.get_chromosome()
                for fitness_function in self._fitness_functions:
                    tch.add_fitness_function(fitness_function)
            else:
                tch = randomness.choice(list(self._archive.solutions)).clone()
                tch.mutate()

            if tch.has_changed():
                offspring_population.append(tch)

        self._logger.info("Number of offsprings = %d", len(offspring_population))
        return offspring_population

    @staticmethod
    def _mutate(offspring: chrom.Chromosome) -> None:
        offspring.mutate()
        if not offspring.has_changed():
            offspring.mutate()

    def _get_non_dominated_solutions(
        self, solutions: List[tcc.TestCaseChromosome]
    ) -> List[tcc.TestCaseChromosome]:
        comparator: DominanceComparator[tcc.TestCaseChromosome] = DominanceComparator(
            goals=self._archive.covered_goals
        )
        next_front: List[tcc.TestCaseChromosome] = []
        for solution in solutions:
            is_dominated = False
            dominated_solutions: List[tcc.TestCaseChromosome] = []
            for best in next_front:
                flag = comparator.compare(solution, best)
                if flag < 0:
                    dominated_solutions.append(best)
                if flag > 0:
                    is_dominated = True
            if is_dominated:
                continue
            next_front.append(solution)
            for dominated_solution in dominated_solutions:
                if dominated_solution in next_front:
                    next_front.remove(dominated_solution)
        return next_front

    def _get_best_individuals(self) -> List[tcc.TestCaseChromosome]:
        return self._get_non_dominated_solutions(self._population)

    def _notify_iteration(self) -> None:
        coverage = len(self._archive.covered_goals) / self._number_of_goals
        self._logger.info(
            "Generation: %5i. Coverage: %5f",
            self._current_iteration,
            coverage,
        )
        StatisticsTracker().set_output_variable_for_runtime_variable(
            RuntimeVariable.CoverageTimeline, coverage
        )
