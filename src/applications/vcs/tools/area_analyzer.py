# -*- coding: utf-8 -*-
import re


class LookupDict(dict):
    """Dictionary lookup object."""

    def __init__(self, name=None):
        self.name = name
        super(LookupDict, self).__init__()

    def __repr__(self):
        return '<lookup \'%s\'>' % (self.name)

    def __getitem__(self, key):
        # We allow fall-through here, so values default to None

        return self.__dict__.get(key, None)

    def get(self, key, default=None):
        return self.__dict__.get(key, default)


_support_langs = {
    # 'java': ('java',),
    # 'javascript': ('js', 'jsx'),
    # 'typescript': ('ts', 'tsx'),
    # 'python': ('py', 'pyx'),

}


support_langs = LookupDict(name=_support_langs)


def _init():
    for code, titles in _support_langs.items():
        for title in titles:
            setattr(support_langs, title, code)
            if not title.startswith(('\\', '/')):
                setattr(support_langs, title.upper(), code)

    def doc(code):
        names = ', '.join('``%s``' % n for n in _support_langs[code])
        return '* %d: %s' % (code, names)

    global __doc__
    __doc__ = (__doc__ + '\n' +
               '\n'.join(doc(code) for code in sorted(_support_langs))
               if __doc__ is not None else None)


_init()


class UnsupportProgrammingLanguage(Exception):
    pass


class AreaCodeAnalyzer(object):

    def __init__(self, filename, content=''):
        self.filename = filename
        self.content = content
        self.lang = self._get_lang()
        self.analyze = self._get_method()

    def _get_lang(self):
        ext = self.filename[self.filename.rfind('.')+1:]
        lang = support_langs[ext]
        if not lang:
            raise UnsupportProgrammingLanguage(
                'Programming language not found for this file: \'{}\''.format(self.filename))
        return lang

    def _get_method(self):
        method = getattr(self, 'analyze_from_{}'.format(self.lang), None)
        if not method:
            raise UnsupportProgrammingLanguage(
                'Programming language analyzer not found for: \'{}\''.format(self.lang))
        return method

    def analyze_from_java(self):
        area_names = list()
        RE_IMPORT = re.compile(r'(?P<type>(import|package))\s(static\s)?(?P<area>.+[^;|\n])', re.MULTILINE)
        for item in RE_IMPORT.finditer(self.content):
            type = item.groupdict()['type']
            area = item.groupdict()['area']
            if type == 'import':
                area = area[:area.rfind('.')]
            area_names.append(area)
        return set(area_names)

