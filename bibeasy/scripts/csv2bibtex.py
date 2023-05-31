#!/usr/bin/env python3
#
# This script converts a csv file (formatted according to the google sheet convention) into a bibtex file that can be
# imported into CCV.
#
# Dependency:
# - Python 3.6 (+ common libraries)
#
# Authors: Julien Cohen-Adad

import pandas as pd
import logging, coloredlogs
import argparse
import re
import fileinput
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase

from bibeasy.utils import SmartFormatter
from bibeasy.utils import display_replacement, get_ref_that_matches_title, replace_ref, parse_num_list


# Initialize logging
coloredlogs.install(fmt='%(asctime)s %(message)s')
logging.basicConfig(level=logging.INFO)


def get_parameters():
    parser = argparse.ArgumentParser(description=
"This script converts a csv file (formatted according to the google sheet convention) into a bibtex file that can be "
"imported into CCV.\n",
                                     formatter_class=SmartFormatter)
    parser.add_argument("-c", "--csv",
                        help="CSV file (e.g. generated from GoogleSheet) which contains indexation used in input.",
                        required=True)
    parser.add_argument("-i", "--id",
                        help="Reference IDs to consider for the conversion. Separate with ',' or to select a block, use"
                             "':'. Examples: 1,3,5:9 --> 1,3,5,6,7,8,9.",
                        required=True)
    return parser.parse_args()


def convert_df_to_db_entries(df):
    """
    Convert Panda dataframe to BibTex db.entries() list according to bibtex convention:
    http://bib-it.sourceforge.net/help/fieldsAndEntryTypes.php

    Example:
    {'journal': 'Nice Journal',
     'comments': 'A comment',
     'pages': '12--23',
     'month': 'jan',
     'abstract': 'This is an abstract. This line should be long enough to test\nmultilines...',
     'title': 'An amazing title',
     'year': '2013',
     'volume': '12',
     'ID': 'Cesar2013',
     'author': 'Jean César',
     'keyword': 'keyword1, keyword2',
     'ENTRYTYPE': 'article'}]

    :param df:
    :return: list of dict
    """
    listbibdic = []
    for index, row in df.iterrows():
        bibdic = {}
        # Enter type-specific fields
        if 'Journal' in row:
            bibdic['journal'] = row['Journal']
            bibdic['ENTRYTYPE'] = 'article'
        elif 'Conference' in row:
            bibdic['organization'] = row['Conference']
            bibdic['ENTRYTYPE'] = 'proceedings'
        else:
            logging.error("Cannot find entry type for entry: {}".format(row))
        # Enter other generic fields
        bibdic['ID'] = str(row['ID'])
        bibdic['author'] = row['Authors']
        bibdic['title'] = row['Title']
        bibdic['year'] = str(int(row['Year']))
        # 'pages': row['Volume:Pages'],
        logging.info("{}: {}".format(bibdic['ID'], bibdic['title']))
        listbibdic.append(bibdic)
    return listbibdic


def main(args):
    """
    Main function
    :param args: See definition in get_parameters()
    :return:
    """

    # Read csv file
    df_csv = pd.read_csv(args.csv, delimiter=',')

    # Remove rows with empty title (those contain NaN)
    df_csv = df_csv.dropna(subset=['Title'])

    # Filter by IDs
    if args.id:
        df_csv = df_csv.query('ID in {}'.format(parse_num_list(args.id)))

    # Write BibTex file
    db = BibDatabase()
    db.entries = convert_df_to_db_entries(df_csv)
    writer = BibTexWriter()
    with open('bibtex.bib', 'w') as bibfile:
        bibfile.write(writer.write(db))


if __name__ == "__main__":
    args = get_parameters()
    main(args)
