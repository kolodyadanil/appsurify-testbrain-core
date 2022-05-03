# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re


class WordInflector(object):
    aberrant_plural_map = {
        'appendix': 'appendices',
        'barracks': 'barracks',
        'cactus': 'cacti',
        'child': 'children',
        'criterion': 'criteria',
        'deer': 'deer',
        'echo': 'echoes',
        'embargo': 'embargoes',
        'focus': 'foci',
        'fungus': 'fungi',
        'goose': 'geese',
        'hero': 'heroes',
        'hoof': 'hooves',
        'index': 'indices',
        'knife': 'knives',
        'dress': 'dresses',
        'life': 'lives',
        'man': 'men',
        'mouse': 'mice',
        'nucleus': 'nuclei',
        'person': 'people',
        'phenomenon': 'phenomena',
        'potato': 'potatoes',
        'self': 'selves',
        'syllabus': 'syllabi',
        'tomato': 'tomatoes',
        'torpedo': 'torpedoes',
        'veto': 'vetoes',
        'woman': 'women',
    }

    aberrant_plural_map.update((item[1], item[0]) for item in list(aberrant_plural_map))
    plurals_suffixes = ['s', 'es', 'ses', 'i', 'ies']
    plurals_suffixes.sort(key=len, reverse=True)
    vowels = set('aeiou')

    @staticmethod
    def _is_inflection_needed(word):
        rules = [r'^\d+$',
                 r'^.$',
                 r'[\w|\d]*[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]$'
                 ]

        for rule in rules:
            if re.match(rule, word):
                return False
        return True

    def _inflect_to_singular(self, word):
        for suffix in self.plurals_suffixes:
            if word == suffix:
                return word
            if word.endswith(suffix):
                if suffix == 'ies':
                    return word[:-len(suffix)] + 'y'
                elif suffix == 'es' and word[-3] == 'v':
                    return word[:-3] + 'f'
                return word[:-len(suffix)]

    def _inflect_to_plural(self, word):
        root = word
        if word[-1] == 'y' and word[-2] not in self.vowels:
            root = word[:-1]
            suffix = 'ies'
        elif word[-1] == 's':
            if word[-2] in self.vowels:
                if word[-3:] == 'ius':
                    root = word[:-2]
                    suffix = 'i'
                else:
                    root = word[:-1]
                    suffix = 'ses'
            else:
                suffix = 'es'
        elif word[-2:] in ('ch', 'sh', 'ss') or word[-1:] == 'x':
            suffix = 'es'
        else:
            suffix = 's'
        plural = root + suffix
        return plural

    def inflect_word(self, word):
        if not self._is_inflection_needed(word):
            return word

        aberrant = self.aberrant_plural_map.get(word)
        if aberrant:
            return aberrant

        singular = self._inflect_to_singular(word)
        if singular:
            return singular
        return self._inflect_to_plural(word)

    def normalize_words(self, words):
        """
        This method convert singular words to plurals and plurals to singulars
        """
        result = []
        for word in words:
            result.append(word)

            aberrant_form = self.aberrant_plural_map.get(word)
            if aberrant_form:
                result.append(aberrant_form)
                continue

            inflected_word = self.inflect_word(word)
            if inflected_word != word:
                result.append(inflected_word)
        return result
