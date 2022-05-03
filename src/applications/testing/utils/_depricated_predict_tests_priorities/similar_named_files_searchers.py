#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#requires python>3.6
#Requires - pip install nltk
#also requires >>> import nltk
#>>> nltk.download('punkt')
#nltk.download('wordnet')
from collections import OrderedDict

from django.db.models import F
from nltk.tokenize import RegexpTokenizer
from nltk.stem.porter import PorterStemmer
from nltk.stem import WordNetLemmatizer

from applications.vcs.models import File

# TODO: add unit tests. Cases:
#   - file matching
#   - folder matching
#   - avoiding stopwords in results

import time
import monotonic
from datetime import timedelta
import logging


time.monotonic = monotonic.monotonic

logger = logging.getLogger(__name__)


class FileTreeIterator(object):
    def __init__(self, project_id):
        self._processed_files = list(File.objects.order_by('tree_id').filter(project_id=project_id, level=0))

    def __iter__(self):
        return self

    def next(self):
        if len(self._processed_files) == 0:
            raise StopIteration()
        cur_file = self._processed_files.pop(0)
        if not cur_file.is_leaf_node():
            self._processed_files.extend(cur_file.get_children())
        return cur_file


class SimilarNamesSearcher(object):
    _stop_words = {'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll",
                  "you'd", 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's",
                  'her', 'hers', 'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs',
                  'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am',
                  'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does',
                  'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while',
                  'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during',
                  'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over',
                  'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how',
                  'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
                  'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don',
                  "don't", 'should', "should've", 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren',
                  "aren't", 'couldn', "couldn't", 'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn',
                  "hasn't", 'haven', "haven't", 'isn', "isn't", 'ma', 'mightn', "mightn't", 'mustn', "mustn't",
                  'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't", 'wasn', "wasn't", 'weren',
                  "weren't", 'won', "won't", 'wouldn', "wouldn't"}

    def __init__(self, project_id):
        self.split_functions = [self.split_punctuation, self.split_camel, self.lem_split]
        self.project_id = project_id

    def split_punctuation(self, value):
        value = self.remove_stop_words(value)
        tokens = RegexpTokenizer(r"\w+").tokenize(value)
        porter = PorterStemmer()
        stemmed_words = set()
        for word in tokens:
            stemmed_word = porter.stem(str(word))
            stemmed_words.add(stemmed_word)
        return stemmed_words

    @staticmethod
    def camel_case_split(string):
        words = [[string[0]]]

        for c in string[1:]:
            if words[-1][-1].islower() and c.isupper():
                words.append(list(c))
            else:
                words[-1].append(c)

        return [''.join(word) for word in words]

    def split_camel(self, value):
        tokens = self.split_punctuation(value)
        split_camel_list = []
        for token in tokens:
            split_camel_list += self.camel_case_split(token)
        final_list = []
        for token in split_camel_list:
            split_values = str(token).split("_")
            final_list += split_values
        porter = PorterStemmer()
        stemmed_words = set()
        for word in final_list:
            stemmed_word = porter.stem(str(word))
            stemmed_words.add(stemmed_word)
        return stemmed_words

    def lem_split(self, value):
        tokens = self.split_camel(value)
        lemmatizer = WordNetLemmatizer()
        return {lemmatizer.lemmatize(str(word)) for word in tokens}

    def remove_stop_words(self, value):
        query_words = value.split()
        result_words = [word for word in query_words if word.lower() not in self._stop_words]
        result = ' '.join(result_words)
        return result

    def get_words(self, obj, attribute):
        obj_name_words = set()
        for split_function in self.split_functions:
            obj_name_words = obj_name_words.union(split_function(getattr(obj, attribute)))
        return obj_name_words

    def get_filename_words(self, filename):
        obj_name_words = set()
        for split_function in self.split_functions:
            obj_name_words = obj_name_words.union(split_function(filename))
        return obj_name_words

    def collect_words_from_attrs(self, obj, attrs):
        obj_words = set()
        for attribute in attrs:
            if not hasattr(obj, attribute):
                raise AttributeError("{0} hasn't this attribute: {1}".format(obj, attribute))
            obj_words = obj_words.union(self.get_words(obj, attribute))
        return obj_words

    # TODO: add ability using mapping between object attrs and result attrs
    def set_similar_words(self, objects, obj_attrs, result_attr):
        """
        :param objects:
        :param obj_attrs:
        :param result_attr:
        :return:
        """
        if not isinstance(result_attr, str):
            raise ValueError(
                "Argument 'result_attr_name' should be string not {0}".format(str(type(result_attr))))

        logger.info('Start re-map attrs for objects')
        map(lambda x: setattr(x, result_attr, set()), objects)

        logger.info('Start .collect_words_from_attrs() per object')
        prepared_objects = [(obj, self.collect_words_from_attrs(obj, obj_attrs)) for obj in objects]

        logger.info('Fetch file tree from DB')
        start_time = time.monotonic()

        file_tree = list(File.objects.order_by('tree_id', 'id').filter(
            project_id=self.project_id, lft=F('rght') - 1).values('filename', 'full_filename')[:10])
        end_time = time.monotonic()

        logger.info('Complete fetch file tree from DB: {} - {} items'.format(
            timedelta(seconds=end_time - start_time), len(file_tree)))

        logger.info('Start foreach Files')
        start_time = time.monotonic()
        for processed_file in file_tree:
            # is_file = processed_file.is_leaf_node()
            # file_words = self.get_words(processed_file, 'filename')
            file_words = self.get_filename_words(processed_file['filename'])
            for obj, words_set in prepared_objects:
                cross_values = words_set.intersection(file_words)
                if len(cross_values) > 0:
                    # if is_file:
                    #     getattr(obj, result_attr).add(processed_file.full_filename)
                    # else:
                    #     files_subset = set(processed_file.get_descendants().filter(children=None).values_list('full_filename', flat=True))
                    #     getattr(obj, result_attr).update(files_subset)
                    getattr(obj, result_attr).add(processed_file['full_filename'])

        end_time = time.monotonic()

        order_dict = OrderedDict({prep[0].value: prep[0].result for prep in prepared_objects})
        logger.info('Complete foreach Files: {}'.format(timedelta(seconds=end_time - start_time)))

    def get_similar_words(self, words):
        logger.info('Start method .get_similar_words')
        attrs = ['value']
        result_attr = 'result'
        object_wrapper = type('test', (object,), {'value': None})
        prepared_objects = []

        for word in words:
            obj = object_wrapper()
            obj.value = word
            prepared_objects.append(obj)

        logger.info('Call method .set_similar_words')
        start_time = time.monotonic()
        self.set_similar_words(prepared_objects, attrs, result_attr)
        end_time = time.monotonic()
        logger.info('Complete .set_similar_words: {}'.format(timedelta(seconds=end_time - start_time)))
        result = {obj.value: obj.result for obj in prepared_objects}
        return result
