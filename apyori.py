#!/usr/bin/env python

"""
Implementation of Apriori algorithm.
"""

import sys
import argparse
import json
from collections import namedtuple
from itertools import combinations
from itertools import chain


__version__ = '0.1.0'
__author__ = 'ymoch'
__author_email__ = 'ymoch@githib.com'


# Ignore name errors because these names are namedtuples.
SupportRecord = namedtuple( # pylint: disable=C0103
    'SupportRecord', ('items', 'support'))
RelationRecord = namedtuple( # pylint: disable=C0103
    'RelationRecord', SupportRecord._fields + ('ordered_statistics',))
OrderedStatistic = namedtuple( # pylint: disable=C0103
    'OrderedStatistic', ('items_base', 'items_add', 'confidence', 'lift',))


class TransactionManager(object):
    """
    Transaction manager class.
    """

    def __init__(self, transactions):
        """
        Initialize.

        @param  transactions    A transaction list.
        """
        self.__num_transaction = 0
        self.__items = []
        self.__transaction_index_map = {}

        for transaction in transactions:
            self.add_transaction(transaction)

    def add_transaction(self, transaction):
        """
        Add a transaction.

        @param  transaction A transaction.
        """
        for item in transaction:
            if item not in self.__transaction_index_map:
                self.__items.append(item)
                self.__transaction_index_map[item] = set()
            self.__transaction_index_map[item].add(self.__num_transaction)
        self.__num_transaction += 1

    def calc_support(self, items):
        """
        Returns a support for items.
        """
        # Empty items is supported by all transactions.
        if not items:
            return 1.0

        # Create the transaction index intersection.
        sum_indexes = None
        for item in items:
            indexes = self.__transaction_index_map.get(item)
            if indexes is None:
                # No support for any set that contains a not existing item.
                return 0.0

            if sum_indexes is None:
                sum_indexes = indexes
            else:
                sum_indexes = sum_indexes.intersection(indexes)

        # Calculate the support.
        return float(len(sum_indexes)) / self.__num_transaction

    def initial_candidates(self):
        """
        Returns the initial candidates.
        """
        return [frozenset([item]) for item in self.__items]

    @property
    def num_transaction(self):
        """
        Returns the number of transactions.
        """
        return self.__num_transaction

    @property
    def items(self):
        """
        Returns the item list that the transaction is consisted of.
        """
        return self.__items

    @staticmethod
    def create(transactions):
        """
        Create the TransactionManager with a transaction instance.
        If the given instance is a TransactionManager, this returns itself.
        """
        if isinstance(transactions, TransactionManager):
            return transactions
        return TransactionManager(transactions)


def create_next_candidates(prev_candidates, length):
    """
    Returns the apriori candidates.
    """
    # Solve the items.
    items = set()
    for candidate in prev_candidates:
        for item in candidate:
            items.add(item)

    def check_subsets(candidate):
        """
        Check if the subsets of a candidate is present
        in the previous candidates.
        """
        candidate_subsets = [
            frozenset(x) for x in combinations(candidate, length - 1)]
        for candidate_subset in candidate_subsets:
            if candidate_subset not in prev_candidates:
                return False
        return True

    # Create candidates.
    next_candidates = []
    for candidate in [frozenset(x) for x in combinations(items, length)]:
        if length > 2 and not check_subsets(candidate):
            continue
        next_candidates.append(candidate)
    return next_candidates


def gen_support_records(
        transaction_manager,
        min_support,
        max_length=None,
        _generate_candidates_func=create_next_candidates):
    """
    Returns a generator of support records with given transactions.
    """
    candidates = transaction_manager.initial_candidates()
    length = 1
    while candidates:
        relations = set()
        for relation_candidate in candidates:
            support = transaction_manager.calc_support(relation_candidate)
            if support < min_support:
                continue
            candidate_set = frozenset(relation_candidate)
            relations.add(candidate_set)
            yield SupportRecord(candidate_set, support)
        length += 1
        if max_length and length > max_length:
            break
        candidates = _generate_candidates_func(relations, length)


def gen_ordered_statistics(transaction_manager, record):
    """
    Returns a generator of ordered statistics.
    """
    items = record.items
    combination_sets = [
        frozenset(x) for x in combinations(items, len(items) - 1)]
    for items_base in combination_sets:
        items_add = frozenset(items.difference(items_base))
        confidence = (
            record.support / transaction_manager.calc_support(items_base))
        lift = confidence / transaction_manager.calc_support(items_add)
        yield OrderedStatistic(
            frozenset(items_base), frozenset(items_add), confidence, lift)


def apriori(transactions, **kwargs):
    """
    Run Apriori algorithm.

    @param  transactions    A list of transactions.
    @param  min_support     The minimum support of the relation (float).
    @param  max_length      The maximum length of the relation (integer).
    """
    min_support = kwargs.get('min_support', 0.1)
    max_length = kwargs.get('max_length', None)
    min_confidence = kwargs.get('min_confidence', 0.0)
    _gen_support_records = kwargs.get(
        '_gen_support_records', gen_support_records)
    _gen_ordered_statistics = kwargs.get(
        '_gen_ordered_statistics', gen_ordered_statistics)

    # Calculate supports.
    transaction_manager = TransactionManager.create(transactions)
    support_records = _gen_support_records(
        transaction_manager, min_support, max_length)

    # Calculate ordered stats.
    for support_record in support_records:
        ordered_statistics = _gen_ordered_statistics(
            transaction_manager, support_record)
        filtered_ordered_statistics = [
            x for x in ordered_statistics if x.confidence >= min_confidence]
        if not filtered_ordered_statistics:
            continue
        yield RelationRecord(
            support_record.items, support_record.support,
            filtered_ordered_statistics)


def dump_as_json(record, output_file):
    """
    Dump an relation record as a json value.

    @param  record      A record.
    @param  output_file An output file.
    """
    def default_func(value):
        """
        Default conversion for JSON value.
        """
        if isinstance(value, frozenset):
            return sorted(value)
        raise TypeError(repr(value) + " is not JSON serializable")

    converted_record = record._replace(
        ordered_statistics=[x._asdict() for x in record.ordered_statistics])
    output_file.write(
        json.dumps(converted_record._asdict(), default=default_func))
    output_file.write('\n')


def dump_as_two_item_tsv(record, output_file):
    """
    Dump a relation record as TSV only for 2 item relations.

    @param  record      A record.
    @param  output_file An output file.
    """
    for ordered_stats in record.ordered_statistics:
        if len(ordered_stats.items_base) != 1:
            return
        if len(ordered_stats.items_add) != 1:
            return
        output_file.write('{0}\t{1}\t{2:.8f}\t{3:.8f}\t{4:.8f}\n'.format(
            list(ordered_stats.items_base)[0], list(ordered_stats.items_add)[0],
            record.support, ordered_stats.confidence, ordered_stats.lift))


def parse_args(argv):
    """
    Parse commandline arguments.
    """
    output_funcs = {
        'json': dump_as_json,
        'tsv': dump_as_two_item_tsv,
    }
    default_output_func_key = 'json'

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-v', '--version', action='version',
        version='%(prog)s {0}'.format(__version__))
    parser.add_argument(
        'input', metavar='inpath', nargs='*',
        help='Input transaction file (default: stdin).',
        type=argparse.FileType('r'), default=[sys.stdin])
    parser.add_argument(
        '-o', '--output', metavar='outpath',
        help='Output file (default: stdout).',
        type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument(
        '-l', '--max-length', metavar='int',
        help='Max length of relations (default: infinite).',
        type=int, default=None)
    parser.add_argument(
        '-s', '--min-support', metavar='float',
        help='Minimum support ratio (must be > 0, default: 0.1).',
        type=float, default=0.1)
    parser.add_argument(
        '-c', '--min-confidence', metavar='float',
        help='Minimum confidence (default: 0.5).',
        type=float, default=0.5)
    parser.add_argument(
        '-d', '--delimiter', metavar='str',
        help='Delimiter for items of transactions (default: tab).',
        type=str, default='\t')
    parser.add_argument(
        '-f', '--out-format', help='Output format (default or tsv).',
        metavar='str', type=str, choices=output_funcs.keys(),
        default=default_output_func_key)
    args = parser.parse_args(argv)
    if args.min_support <= 0:
        raise ValueError('min support must be > 0')

    args.output_func = output_funcs[args.out_format]
    return args


def main():
    """
    Main.
    """
    args = parse_args(sys.argv[1:])

    transactions = [
        line.strip().split(args.delimiter) for line in chain(*args.input)]
    result = apriori(
        transactions,
        max_length=args.max_length,
        min_support=args.min_support,
        min_confidence=args.min_confidence)

    for record in result:
        args.output_func(record, args.output)


if __name__ == '__main__':
    main()