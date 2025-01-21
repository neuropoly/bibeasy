#!/usr/bin/env python
#
# List of utilities useful for this package

import argparse
import logging
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from bibeasy.formatting import csv_to_txt_pubtype
from bibeasy.gsheet import CACHED_GSHEET

ET.register_namespace("generic-cv", "http://www.cihr-irsc.gc.ca/generic-cv/1.0.0") # this helps the CCV XML write() right

CCV_REF_TYPE = ['Journal Articles', 'Conference Publications']
usertype2ccvtype = {'article': 'Journal Articles', 'proceedings': 'Conference Publications'}
ccvtype2usertype = {'Journal Articles': 'article', 'Conference Publications': 'proceedings'}

# Associates the string with prefix used in input text file
usertype2prefix = {'article': 'J',
                   'proceedings': 'C',
                   'talk': 'T',
                   'bookchapter': 'B',
                   }
CCVTYPE2PREFIX = {'Journal Articles': 'J', 'Conference Publications': 'C'}


class bcolors:
    normal = '\033[0m'
    red = '\033[91m'
    yellow = '\033[93m'
    green = '\033[92m'


class SmartFormatter(argparse.HelpFormatter):
    """
    Custom formatter that inherits from HelpFormatter, which adjusts the default width to the current Terminal size,
    and that gives the possibility to bypass argparse's default formatting by adding "R|" at the beginning of the text.
    Inspired from: https://pythonhosted.org/skaff/_modules/skaff/cli.html
    """
    def __init__(self, *args, **kw):
        self._add_defaults = None
        super(SmartFormatter, self).__init__(*args, **kw)
        # Update _width to match Terminal width
        try:
            self._width = shutil.get_terminal_size()[0]
        except (KeyError, ValueError):
            logging.warning('Not able to fetch Terminal width. Using default: %s'.format(self._width))

    # this is the RawTextHelpFormatter._fill_text
    def _fill_text(self, text, width, indent):
        # print("splot",text)
        if text.startswith('R|'):
            paragraphs = text[2:].splitlines()
            rebroken = [argparse._textwrap.wrap(tpar, width) for tpar in paragraphs]
            rebrokenstr = []
            for tlinearr in rebroken:
                if (len(tlinearr) == 0):
                    rebrokenstr.append("")
                else:
                    for tlinepiece in tlinearr:
                        rebrokenstr.append(tlinepiece)
            return '\n'.join(rebrokenstr)  # (argparse._textwrap.wrap(text[2:], width))
        return argparse.RawDescriptionHelpFormatter._fill_text(self, text, width, indent)

    # this is the RawTextHelpFormatter._split_lines
    def _split_lines(self, text, width):
        if text.startswith('R|'):
            return text[2:].splitlines()
        return argparse.HelpFormatter._split_lines(self, text, width)


def csv_to_txt(
        df_csv, pubtypes: Optional[list[str]], combine: bool,
        output: Path, labels: Optional[Path], style: str
):
    """
    Write formatted output file with list of publication.
    """
    # If no subtypes were defined, use all available
    if pubtypes is None or len(pubtypes) < 1:
        pubtypes = set(df_csv['Type'])

    # Iterate across pubtypes and write output file
    for pubtype in pubtypes:
        sub_db = df_csv[df_csv['Type'] == pubtype]
        csv_to_txt_pubtype(sub_db, pubtype, output, labels, style)
    #Sort df descending for wiki output
    if combine:
        df_csv = df_csv.sort_values(['Year'], ascending=False)
        csv_to_txt_pubtype(df_csv, 'combined', output, labels, style)

def display_ref(df, input_refs: List[str]):
    """
    Display reference.
    :param df:
    :param input_refs: String or file name containing a list of references.
    :return:
    """
    # Read input text file
    for line in input_refs:
        # Find all refs that have J or C as prefix, followed by an integer
        list_ref_id = []
        for prefixtype in list(usertype2prefix.values()):
            list_ref_id.append(re.findall(prefixtype + '\d+', line))
        # Flatten list
        list_ref_id = [val for sublist in list_ref_id for val in sublist]

        # Display ref
        if list_ref_id:
            for ref_id in list_ref_id:
                ref = df[df['ID'] == ref_id]
                if ref.shape[0] < 1:
                    logging.warning(f"No entries in GSheet Cache matched reference ID '{ref_id}'; skipping!")
                else:
                    print("{:<5s}{}..., {}".format(
                        ref_id,
                        ref['Authors'].to_numpy()[0].split(',')[0],
                        ref['Title'].to_numpy()[0]))


def display_replacement(df_old, id_old, id_new):
    """
    Display replacement results (with fancy colors). If ccv_ref_id=-1, it means no match (outputs warning)
    :param pandas DF
    :param id_old: int: Old reference ID
    :param id_new: int: New reference ID
    :return: None
    """
    csv_ref_title = ''
    if id_new == '?':
        color_disp = bcolors.red
    # elif id_new == -2:
    #     color_disp = bcolors.yellow
    #     csv_ref_title = '?'
    else:
        color_disp = bcolors.green
    if not csv_ref_title:
        # panda object
        csv_ref_title = df_old[df_old['ID'] == id_old]['Title'].values[0]
    print(color_disp + str(id_old) + "->" + str(id_new) + ": " + csv_ref_title + bcolors.normal)


def find_matching_ref(df_csv, df_ccv, pubtypes):
    """
    Get the CCV ID that matches the input row
    :param df_csv: Pandas dataframe: DF of GoogleSheet CSV
    :param df_ccv: Pandas dataframe: DF of CCV
    :param pubtypes: list: Can contain the following items: {'article', 'proceedings'}.
    :return: dict: ID conversion from CSV to CCV
    """
    # df_ccv[(df_ccv['Title'] == row['Title']) & (df_ccv['Journal' == row['Journal']])]
    check_mismatched_fields = ['Authors', 'Journal/Conference']

    # If no pubtype was specified, check only articles and proceedings
    # TODO Move this (and several other identical checks) elsewhere to reduce redundancy
    if pubtypes is None or len(pubtypes) < 1:
        pubtypes = ['article', 'proceedings']

    for pubtype in pubtypes:
        # medium_type = {'article': 'Journal', 'proceedings': 'Conference'}
        logging.info("\nPublication type: '{}'\n".format(pubtype))
        # First, loop across CSV refs
        csv2ccv = {}
        n_found, n_missed, n_duplicate = 0, 0, 0
        df_ccv_unmatched = df_ccv[df_ccv['Type'] == pubtype].copy()
        for _, row in df_csv[df_csv['Type'] == pubtype].iterrows():
            mismatch = []
            # TODO: check with more than Title
            # TODO: add matching pubtype
            id_ccv = df_ccv[
                (df_ccv['Type'] == row['Type']) &
                (df_ccv['Title'] == row['Title'])
                ].index.values

            # It is possible that the same title was used for more that one publication. So, filter out by journal/conf
            if len(id_ccv) >= 2:
                for id_ccv_single in id_ccv:
                    if df_ccv['Journal/Conference'][id_ccv_single] == row['Journal/Conference']:
                        id_ccv = np.array(id_ccv_single)
                        break

            # If a unique match was found
            if len(id_ccv) == 1:
                logging_info = True
                csv2ccv[row['ID']] = df_ccv['ID'][id_ccv[0]]
                df_ccv_unmatched = df_ccv_unmatched.drop(id_ccv[0])
                n_found += 1
                # Check for other fields
                for check_mismatched_field in check_mismatched_fields:
                    if not df_ccv[check_mismatched_field][id_ccv[0]] == row[check_mismatched_field]:
                        mismatch.append(check_mismatched_field)
            else:
                logging_info = False
                if len(id_ccv) == 0:
                    csv2ccv[row['ID']] = 'missed'
                    n_missed += 1
                elif len(id_ccv) >= 2:
                    csv2ccv[row['ID']] = 'dupl'
                    n_duplicate += 1
            strprint = "GSHEET {}\tCCV {}\t{}".format(
                row['ID'],
                csv2ccv[row['ID']],
                row['Title'])
            # TODO: do logging type for warning
            if logging_info:
                logging.info(strprint)
            else:
                logging.critical(strprint)
            if mismatch:
                logging.warning("  Mismatched fields: {}".format(', '.join(mismatch)))

        # List refs present in CCV but not in GSHEET
        for _, row in df_ccv_unmatched.iterrows():
            logging.warning("GSHEET [missed]\tCCV {}\t{}".format(row['ID'], row['Title']))

        # Display items
        print("\nResults for type: '{}': Found: {} | Not in CCV: {} | Duplicate: {} | Not in Gsheet: {}\n".format(
            pubtype, n_found, n_missed, n_duplicate, len(df_ccv_unmatched)))

    return csv2ccv


def find_ref_blocks(txt):
    """
    Find blocks of references, separated by '[X...]', with X being one of the allowed reference prefix, and output a
    list of list of refs.
    "Blablabla [J1, J5] pouf pouf [C45] yay!" --> ['J1, J5', 'C45']
    :param txt:
    :return:
    """
    # TODO: add test
    txt_splitl = txt.split('[')[1:]
    return [a.split(']')[0] for a in txt_splitl]


def fix_input_ref(inputref_arg):
    """
    Figure out if inputref_arg is a file name or a list of refs (string)
    :param inputref_arg:
    :return: string, which is a file name of a string of ref: "[J1, J4, J6]"
    """
    # TODO: add test
    if len(inputref_arg) > 1:
        return " ".join(inputref_arg)
    return inputref_arg[0]


def xml_to_df(xml_path: Path):
    """
    Import XML CCV structure into custom DataFrame
    :param xml_path: Path to the XML file to parse
    :return:
    """
    # Check to make sure the file actually exists, and raise an error if its doesn't
    if not xml_path.exists():
        raise ValueError("Path provided for the CCV XML does not exist, and could not be read!")

    # the title is found either in the 'Journal' or 'Conference Name' <field>,
    # depending on what kind of publication it was, hence field_journalconf.
    field_title = {'Journal Articles': 'Article Title',
                   'Conference Publications': 'Publication Title'}
    # ditto, but for the venue
    field_venue = {'Journal Articles': 'Journal',
                   'Conference Publications': 'Conference Name'}

    # Read XML file (CCV references)
    xml = ET.parse(xml_path)
    publications = xml.getroot().find("./section[@label='Contributions']/section[@label='Publications']")

    refcounters = {reftype: 0 for reftype in CCV_REF_TYPE}
    obj_lst = []
    for p in publications:
        reftype = p.attrib['label']
        if reftype not in CCV_REF_TYPE: continue
        refcounters[reftype]+=1

        authors = p.find("./field[@label='Authors']/value").text
        title = p.find(f"./field[@label='{field_title[reftype]}']/value").text
        venue = p.find(f"./field[@label='{field_venue[reftype]}']/value").text
        obj_lst.append({
            'ID': CCVTYPE2PREFIX[reftype] + str(refcounters[reftype]),
            'Type': ccvtype2usertype[reftype],
            'Authors': authors,
            'Title': title,
            'Journal/Conference': venue,
            })

    df_xml = pd.DataFrame(obj_lst)

    return df_xml


def get_db_from_csv(fname_csv):
    """
    Get pandas DB from csv file
    :param fname_csv:
    :return:
    """
    df_publis = pd.read_csv(fname_csv, delimiter=',')
    for hh in range(0, len(df_publis)):
        print(hh)
        authors = df_publis['Authors'][hh]
        title = df_publis['Title'][hh]
        conference = df_publis['Conference'][hh]
        date = str(df_publis['Date'][hh])


def parse_num_list(str_num):
    """
    Parse numbers in string based on delimiter: , or :
    Examples:
      '' -> []
      '1,2,3' -> [1, 2, 3]
      '1:3,4' -> [1, 2, 3, 4]
      '1,1:4' -> [1, 2, 3, 4]
    :param str_num: string
    :return: list of ints
    """
    list_num = list()

    if not str_num:
        return list_num

    elements = str_num.split(",")
    for element in elements:
        m = re.match(r"^\d+$", element)
        if m is not None:
            val = int(element)
            if val not in list_num:
                list_num.append(val)
            continue
        m = re.match(r"^(?P<first>\d+):(?P<last>\d+)$", element)
        if m is not None:
            a = int(m.group("first"))
            b = int(m.group("last"))
            list_num += [ x for x in range(a, b+1) if x not in list_num ]
            continue
        raise ValueError("unexpected group element {} group spec {}".format(element, str_num))

    return list_num


def replace_ref_in_text(df_old, df_new, input_refs, sort_ref=False):
    """
    Display reference.
    :param df_old:
    :param df_new:
    :param input_refs: String or file name containing a list of references.
    :param sort_ref: Bool
    :return:
    """
    # If input_refs is a file, find references using regex
    # Read input text file
    for line in input_refs:
        # Find blocks of refs
        ref_blocks = find_ref_blocks(line)
        # Loop across blocks and replace refs
        for ref_block in ref_blocks:
            list_ref_old = ref_block.split(', ')
            list_ref_new = []
            for id_old in list_ref_old:
                ref_old = df_old[df_old['ID'] == id_old]
                # Find entries with the same Title
                ref_new = df_new[df_new['Title'].isin(ref_old['Title'])]
                # Within these entries, find those with the same Journal
                # TODO: put it back, with more checks...
                # ref_new = ref_new[ref_new['Journal/Conference'].isin(ref_old['Journal/Conference'])]
                # At this point, there should be no more than one entry. Assign new ID
                # TODO: check if this is true
                if len(ref_new['ID'].values):
                    id_new = ref_new['ID'].values[0]
                else:
                    id_new = '?'
                # Make sure this row hasn't been filtered
                # line = replace_ref(line, id_old, id_new)
                list_ref_new.append(id_new)
                # TODO: run display_replacement in replace_ref
                display_replacement(df_old, id_old, id_new)
            # Sort
            # TODO: improve sorting to account for variable number of units, and per publication type
            if sort_ref:
                list_ref_new.sort()
            # Generate new block with replaced refs
            ref_block_new = ', '.join(list_ref_new)
            # Replaced old with new block instances
            line = line.replace(ref_block, ref_block_new)
        print(line)


def sync(df_csv, fname_xml):
    """
    Copy fields from df_csv into fname_xml.

    :param df_csv: a pandas.DataFrame containing a loaded citation database.
    :param fname_xml: a filename of a ccv-cvc.ca -generated XML file containing a Curriculum Vitae.
    """

    # the title is found either in the 'Journal' or 'Conference Name' <field>,
    # depending on what kind of publication it was, hence field_journalconf.
    field_title = {'Journal Articles': 'Article Title',
                   'Conference Publications': 'Publication Title',
                   }
    # ditto, but for the venue
    field_venue = {'Journal Articles': 'Journal',
                   'Conference Publications': 'Conference Name',
                   }

    xml = ET.parse(fname_xml) # preparse the XML so that xml_to_df doesn't have to load it a second time.

    publications = xml.getroot().find("./section[@label='Contributions']/section[@label='Publications']")

    for p in publications:
        reftype = p.attrib['label']

        if reftype not in ccvtype2usertype: continue # skip unhandled publication types

        # Instead of calling find_matching_ref(), which forces wastefully calling xml_to_df(),
        # repeat its key logic.
        title = p.find(f"./field[@label='{field_title[reftype]}']/value").text
        query = (df_csv['Type'] == ccvtype2usertype[reftype]) & (df_csv['Title'] == title)

        row = df_csv[query]
        if len(row) == 0:
            # not found.
            # TODO: create?
            continue
        elif len(row) > 1:
            query = (row['Journal/Conference'] == p.find(f"./field[@label='{field_venue[reftype]}']/value").text)
            row = row[query]
            if len(row) == 1:
                pass
            else:
                raise ValueError("Could not disambiguate publication {repr(title)} found in CCV XML.")

        assert len(row) == 1

        # exact match. update
        authors, venue = row[['Authors','Journal/Conference']].values[0] # pandas confuses me??

        logging.info("\nUpdating {}".format(repr(title)))

        logging.info("Authors: {} => {}".format(p.find("./field[@label='Authors']/value").text, authors))
        p.find("./field[@label='Authors']/value").text = authors

        logging.info("{}: {} => {}".format(field_venue[reftype], p.find(f"./field[@label='{field_venue[reftype]}']/value").text, venue))
        p.find(f"./field[@label='{field_venue[reftype]}']/value").text = venue

    xml.write(fname_xml, xml_declaration=True)


def excel_to_df(excel_source: pd.ExcelFile, type_filter: list[str]):
    """
    Read and format an Excel spreadsheet into the format expected for the rest of the program
    :param excel_source: The pandas Excel file manager to parse
    :param type_filter: The types of publication (subsheets in the file) which should be read
    :return:
    """
    # If no ExcelSource is provided, try to load it from the cache
    # If no input was provided, assume the user wants to use the existing GSheet Cache
    if excel_source is None:
        if CACHED_GSHEET.exists():
            logging.info("Using cached Google Sheet results as input, as no other input source was specified!")
            excel_source = pd.ExcelFile(CACHED_GSHEET)
        else:
            raise ValueError("No input source was specified, and no cache exists to pull from. "
                             "Please define either a URL to a public Google Sheet, or Excel spreadhseet file.")

    # If the user didn't explicitly request a subset of publication types, use all of them
    if type_filter is None or len(type_filter) < 1:
        type_filter = excel_source.sheet_names

    # Otherwise, check if any sheets requested by the user are not present, and raise an error if any are found
    else:
        invalid_types = set(type_filter) - set(excel_source.sheet_names)
        if len(invalid_types) > 0:
            raise ValueError(
                f"Requested publication types '{invalid_types}' which do not exist in the cache. "
                f"Valid publication types are '{set(excel_source.sheet_names)}' for this file. "
                f"Check for typos, and confirm that the cache is up-to-date!"
            )

    # Iterate through the requested sheets, preparing them to be concatenated
    sub_dfs = []
    for type_id in type_filter:
        # Read the sub-sheet DataFrame
        sub_df = pd.read_excel(excel_source, type_id)

        # Set the 'type' of the sub_df to the sheet's name
        sub_df['Type'] = type_id

        # Store the result in a list to be stacked later
        sub_dfs.append(sub_df)

        # Log the size of the result for the user
        logging.info(f"\tTotal '{type_id}' entries: {sub_df.shape[0]}")

    # Concatenate them all together into one full dataframe
    return_df = pd.concat(sub_dfs, ignore_index=True)

    return return_df
