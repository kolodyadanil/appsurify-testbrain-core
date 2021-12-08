# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
from django.test import SimpleTestCase
from applications.api.testing.wordinflector import WordInflector


class TestWordInflector(SimpleTestCase):
    @unittest.expectedFailure
    def test_match_words_normalization(self):
        assertions_msgs = []
        words_pairs = [('123', '123'),
                       ('x', 'x'),
                       ('some_word?', 'some_word?'),
                       ('some_word@', 'some_word@'),

                       ('fox', 'foxes'),
                       ('foxes', 'fox'),
                       ('dress', 'dresses'),
                       ('dresses', 'dress'),
                       ('bench', 'benches'),
                       ('benches', 'bench'),
                       ('dish', 'dishes'),
                       ('dishes', 'dish'),

                       ('cherry', 'cherries'),
                       ('cherries', 'cherry'),
                       ('puppy', 'puppies'),

                       ('monkey', 'monkeys'),
                       ('monkeys', 'monkey'),
                       ('toy', 'toys'),
                       ('toys', 'toy'),
                       ('day', 'days'),
                       ('days', 'day'),

                       ('pistachio', 'pistachios'),
                       ('pistachios', 'pistachio'),
                       ('stereo', 'stereos'),
                       ('stereos', 'stereo'),

                       ('hero', 'heroes'),
                       ('heroes', 'hero'),
                       ('piano', 'pianos'),
                       ('pianos', 'piano'),

                       ('wife', 'wives'),
                       ('wives', 'wife'),
                       ('knife', 'knives'),
                       ('knives', 'knife'),
                       ('elf', 'elves'),
                       ('elves', 'elf'),
                       ('loaf', 'loaves'),
                       ('loaves', 'loaf'),
                       ('chef', 'chefs'),
                       ('chefs', 'chef'),
                       ('cliff', 'cliffs'),
                       ('cliffs', 'cliff'),
                       ('puff', 'puffs'),
                       ('puffs', 'puff'),

                       ('test', 'tests'),
                       ('tests', 'test'),

                       ('woman', 'women'),
                       ('women', 'woman'),
                       ]
        inflector = WordInflector()
        for word, expected_word in words_pairs:
            inflected_word = inflector.inflect_word(word)
            if inflected_word != expected_word:
                assertions_msgs.append(
                    "\n'word': %s |'inflected_word': %s | 'expected_word': %s" % (word, inflected_word, expected_word))

        assert_flag = True if len(assertions_msgs) > 0 else False
        self.assertFalse(assert_flag, ''.join(assertions_msgs))
