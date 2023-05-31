#!/usr/bin/env python3
#
# Convert reference ID from one CCV version to another CCV version.
#
# Author: Julien Cohen-Adad


import logging
import coloredlogs
import argparse

from bibeasy.utils import SmartFormatter, xml_to_df, replace_ref_in_text


# Initialize logging
coloredlogs.install(fmt='%(asctime)s %(message)s')
logging.basicConfig(level=logging.INFO)


def get_parameters():
    parser = argparse.ArgumentParser(description=
"Convert reference ID from one CCV version to another CCV version.\n",
                                     formatter_class=SmartFormatter)
    parser.add_argument('xmlsrc',
                        type=argparse.FileType('r'),
                        help="XML source file (associated with input references).")
    parser.add_argument('xmldest',
                        type=argparse.FileType('r'),
                        help="XML destination file.")
    parser.add_argument("-i", "--input",
                        help="Text file which contains references, listed as: '[J12, J13, C8], [J74]', where 'J' "
                             "corresponds to journal publications and 'C' corresponds to conference proceedings.",
                        required=False)
    return parser.parse_args()


def main():
    args = get_parameters()
    df_src = xml_to_df(args.xmlsrc)
    df_dest = xml_to_df(args.xmldest)
    replace_ref_in_text(df_src, df_dest, args.input)


if __name__ == "__main__":
    main()
