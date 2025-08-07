# -*- coding: utf-8 -*-
# Author: Francois Boulogne
# License:


import logging
from enum import Enum, auto
from typing import Dict, Callable, Iterable, Union
from bibtexparser.bibdatabase import (BibDatabase, COMMON_STRINGS,
                                      BibDataString,
                                      BibDataStringExpression)


logger = logging.getLogger(__name__)

__all__ = ['BibTexWriter']

# A list of entries that should not be included in the content (key = value) of a BibTex entry
ENTRY_TO_BIBTEX_IGNORE_ENTRIES = ['ENTRYTYPE', 'ID']


class SortingStrategy(Enum):
    """
    Defines different strategies for sorting the entries not defined in :py:attr:`~.BibTexWriter.display_order` and that are added at the end.
    """
    ALPHABETICAL_ASC = auto()
    """
    Alphabetical sorting in ascending order.
    """
    ALPHABETICAL_DESC = auto()
    """
    Alphabetical sorting in descending order.
    """
    PRESERVE = auto()
    """
    Preserves the order of the entries. Entries are not sorted.
    """


def _apply_sorting_strategy(strategy: SortingStrategy, items: Iterable[str]) -> Iterable[str]:
    """
    Sorts the items based on the given sorting strategy.
    """
    if strategy == SortingStrategy.ALPHABETICAL_ASC:
        return sorted(items)
    elif strategy == SortingStrategy.ALPHABETICAL_DESC:
        return reversed(sorted(items))
    elif strategy == SortingStrategy.PRESERVE:
        return items
    else:
        raise NotImplementedError(f"The strategy {strategy.name} is not implemented.")


def to_bibtex(parsed):
    """
    Convenience function for backwards compatibility.
    """
    return BibTexWriter().write(parsed)


def _str_or_expr_to_bibtex(e):
    if isinstance(e, BibDataStringExpression):
        return ' # '.join([_str_or_expr_to_bibtex(s) for s in e.expr])
    elif isinstance(e, BibDataString):
        return e.name
    else:
        return '{' + e + '}'


class BibTexWriter(object):
    """
    Writer to convert a :class:`BibDatabase` object to a string or file formatted as a BibTeX file.

    Example::

        from bibtexparser.bwriter import BibTexWriter

        bib_database = ...

        writer = BibTexWriter()
        writer.contents = ['comments', 'entries']
        writer.indent = '  '
        writer.order_entries_by = ('ENTRYTYPE', 'author', 'year')
        bibtex_str = bibtexparser.dumps(bib_database, writer)

    """

    _valid_contents = ['entries', 'comments', 'preambles', 'strings']

    def __init__(self, write_common_strings=False):
        #: List of BibTeX elements to write, valid values are `entries`, `comments`, `preambles`, `strings`.
        self.contents = ['comments', 'preambles', 'strings', 'entries']
        #: Character(s) for indenting BibTeX field-value pairs. Default: single space.
        self.indent = ' '
        #: Align values. Aligns all values according to a given length by padding with single spaces.
        #    If align_values is true, the maximum number of characters used in any field name is used as the length.
        #    If align_values is a number, the greater of the specified value or the number of characters used in the
        #    field name is used as the length.
        #    Default: False
        self.align_values: Union[int, bool] = False
        #: Align multi-line values. Formats a multi-line value such that the text is aligned exactly
        #    on top of each other. Default: False
        self.align_multiline_values = False
        #: Characters(s) for separating BibTeX entries. Default: new line.
        self.entry_separator = '\n'
        #: Tuple of fields for ordering BibTeX entries. Set to `None` to disable sorting. Default: BibTeX key `('ID', )`.
        self.order_entries_by = ('ID', )
        #: Tuple of fields for display order in a single BibTeX entry. Fields not listed here will be displayed at the
        #    end in the order defined by display_order_sorting. Default: '[]'
        self.display_order = []
        # Sorting strategy for entries not contained in display_order. Entries not defined in display_order are added
        #    at the end in the order defined by this strategy. Default: SortingStrategy.ALPHABETICAL_ASC
        self.display_order_sorting: SortingStrategy = SortingStrategy.ALPHABETICAL_ASC
        #: BibTeX syntax allows comma first syntax
        #: (common in functional languages), use this to enable
        #: comma first syntax as the bwriter output
        self.comma_first = False
        #: BibTeX syntax allows the comma to be optional at the end of the last field in an entry.
        #: Use this to enable writing this last comma in the bwriter output. Defaults: False.
        self.add_trailing_comma = False
        #: internal variable used if self.align_values = True or self.align_values = <number>
        self._max_field_width = 0
        #: Whether common strings are written
        self.common_strings = write_common_strings

    def write(self, bib_database):
        """
        Converts a bibliographic database to a BibTeX-formatted string.

        :param bib_database: bibliographic database to be converted to a BibTeX string
        :type bib_database: BibDatabase
        :return: BibTeX-formatted string
        :rtype: str or unicode
        """
        bibtex = ''
        for content in self.contents:
            try:
                # Add each element set (entries, comments)
                bibtex += getattr(self, '_' + content + '_to_bibtex')(bib_database)
            except AttributeError:
                logger.warning("BibTeX item '{}' does not exist and will not be written. Valid items are {}."
                               .format(content, self._valid_contents))
        return bibtex

    def _entries_to_bibtex(self, bib_database):
        if self.order_entries_by:
            # TODO: allow sort field does not exist for entry
            entries = sorted(bib_database.entries, key=lambda x: BibDatabase.entry_sort_key(x, self.order_entries_by))
        else:
            entries = bib_database.entries

        if self.align_values is True:
            # determine maximum field width to be used
            widths = [len(ele) for entry in entries for ele in entry if ele not in ENTRY_TO_BIBTEX_IGNORE_ENTRIES]
            self._max_field_width = max(widths)
        elif type(self.align_values) == int:
            # Use specified value
            self._max_field_width = self.align_values

        return self.entry_separator.join(self._entry_to_bibtex(entry) for entry in entries)

    def _entry_to_bibtex(self, entry):
        bibtex = ''
        # Write BibTeX key
        bibtex += '@' + entry['ENTRYTYPE'] + '{' + entry['ID']

        # create display_order of fields for this entry
        # first those keys which are both in self.display_order and in entry.keys
        display_order = [i for i in self.display_order if i in entry]
        # then all the other fields sorted alphabetically
        display_order += [i for i in _apply_sorting_strategy(self.display_order_sorting, entry) if i not in self.display_order]
        if self.comma_first:
            field_fmt = u"\n{indent}, {field:<{field_max_w}} = {value}"
        else:
            field_fmt = u",\n{indent}{field:<{field_max_w}} = {value}"
        # Write field = value lines
        for field in [i for i in display_order if i not in ENTRY_TO_BIBTEX_IGNORE_ENTRIES]:
            max_field_width = max(len(field), self._max_field_width)
            try:
                value = _str_or_expr_to_bibtex(entry[field])

                if self.align_multiline_values:
                    # Calculate indent of multi-line values. Text from a multiline string
                    # should be aligned, i.e., be exactly on top of each other.
                    # E.g.:       title = {Hello
                    #                      World}
                    # Calculate the indent of "World":
                    # Left of field (whitespaces before e.g. 'title')
                    value_indent = len(self.indent) + max_field_width
                    # Right of field ' = ' (<- 3 chars) + '{' (<- 1 char)
                    value_indent += 3 + 1

                    value = value.replace('\n', '\n' + value_indent * ' ')

                bibtex += field_fmt.format(
                    indent=self.indent,
                    field=field,
                    field_max_w=max_field_width,
                    value=value)
            except TypeError:
                raise TypeError(u"The field %s in entry %s must be a string"
                                % (field, entry['ID']))
        if self.add_trailing_comma:
            if self.comma_first:
                bibtex += '\n'+self.indent+','
            else:
                bibtex += ','
        bibtex += "\n}\n"
        return bibtex

    def _comments_to_bibtex(self, bib_database):
        return ''.join(['@comment{{{0}}}\n{1}'.format(comment, self.entry_separator)
                        for comment in bib_database.comments])

    def _preambles_to_bibtex(self, bib_database):
        return ''.join(['@preamble{{"{0}"}}\n{1}'.format(preamble, self.entry_separator)
                        for preamble in bib_database.preambles])

    def _strings_to_bibtex(self, bib_database):
        return ''.join([
            u'@string{{{name} = {value}}}\n{sep}'.format(
                name=name,
                value=_str_or_expr_to_bibtex(value),
                sep=self.entry_separator)
            for name, value in bib_database.strings.items()
            if (self.common_strings or
                name not in COMMON_STRINGS or  # user defined string
                value != COMMON_STRINGS[name]  # string has been updated
                )])
