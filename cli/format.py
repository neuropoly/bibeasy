###
# Author: Julien Cohen-Adad, Kalum Ost, Nathan Gorvett
###
import logging
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
from textwrap import dedent
from typing import Optional

import coloredlogs
import pandas as pd
import requests
from xdg.BaseDirectory import save_cache_path

import bibeasy.gsheet as bibsheet
import bibeasy.utils
from bibeasy.formatting import df_to_docx, df_to_neuro_md

# Global Constants to track where cached data is kept
CACHE_PATH = Path(save_cache_path('bibeasy'))
CACHED_GSHEET = CACHE_PATH / "gsheet.xlsx"

# Map of currently supported formats and their formatting calls
FORMAT_CALLS = {
    "docx": df_to_docx,
    "neuro_md": df_to_neuro_md
}

# == Utilities == #
def cache_gsheet(url_result):
    # Cache the result before proceeding
    logging.info(f"Caching Google Sheet at designated URL...")
    with open(CACHED_GSHEET, "wb") as fd:
        fd.write(url_result.content)
    # Return the result as a managed ExelFile
    return pd.ExcelFile(CACHED_GSHEET)


# == CLI Argument Helpers == #
def cli_excel_input_path_or_url(val: Optional[str]) -> pd.ExcelFile:
    # Try to pull from a URL first
    url_result = requests.get(f"{val}/export?format=xlsx")

    # If we succeed, use the data from that URL as the CLI's result
    if url_result.status_code == 200:
        return cache_gsheet(url_result)
    # Otherwise, assume the input refers to a file and try and load that instead
    else:
        val_path = Path(val)
        # Terminate if the provided path does not exist
        if not val_path.exists():
            raise ValueError(f"The provided input '{val_path}' is not a valid GSheet URL or path.")
        # Terminate if the provided path is not a valid file
        elif not val_path.is_file():
            raise ValueError(f"The provided input '{val_path}' exists, but is not a valid file.")
        # Wrap the file in a pandas ExcelFile for easy parsing later
        return pd.ExcelFile(val_path)


# == Main CLI Parsing == #
def parse_cli_arguments():
    parser = ArgumentParser(
        description="Reformat the contents of one bibliography file into another (new) file.",
        epilog=dedent("""
            Usage:
            ======
            ----------------
            Common Use Cases
            ----------------
            Converting a Google Sheet's contents into Word (caching it in the process)
            > bibeasy_format -i docs.google.com/spreadsheet... -f docx
            
            Save the output files in a designated directory (using the cached result from the prior command)
            > bibeasy_format -f docx -o ./biblio_out
            
            Change the name of the output files to be "biblio"
            > bibeasy_format -f docx -l biblio
            
            ------------------
            Supported Formats
            ------------------
            Converting a Google Sheet's contents into Word
            > bibeasy_format -f docx
            
            Converting a Google Sheet's contents into the NeuroPoly Website's MarkDown format
            > bibeasy_format -f neuro_md
            
            ------------------------
            Filtering and Structuring
            ------------------------
            Filter the output to only have entries from 2015 and onward
            > bibeasy_format -f docx --year 2015
            
            Filter to only contain articles and talks.
            These are checked against the sheet names in your Google/Excel SpreadSheet!
            > bibeasy_format -f docx -t article talk
            
            Filter to only contain entries where the 'IVADO17' column is an x
            > bibeasy_format -f docx --filters "IVADO17 == 'x'"
            
            Reverse the order of the output, from most to least recently published
            > bibeasy_format -f docx --reverse
            
            Separate the results into multiple outputs, based on their type (i.e. conference article)
            > bibeasy_format -f docx --keep_separate 
            
            Format the output in the APA citation style:
            > bibeasy_format -f docx --style APA
        """),
        # This prevents newlines from being stripped from the epilog!
        formatter_class=RawTextHelpFormatter
    )

    # Core arguments
    parser.add_argument(
        '-i', '--input', dest="input_excel", type=cli_excel_input_path_or_url, default=None,
        help="The initial bibliography data to read, as either a path to a file or URL to a public Google Sheet."
             "If not specified, will try and load the most recently cached Google Sheet created from using this command."
    )
    parser.add_argument(
        '-f', '--format', dest="output_format", type=str, required=True, choices=FORMAT_CALLS.keys(),
        help="The file format the output should be put into."
    )
    parser.add_argument(
        '-o', '--output', dest="output_path", type=Path, default=Path('.'),
        help="The directory all output files should be placed into. Defaults to the current directory."
    )
    parser.add_argument(
        '-l', '--label', dest="out_label", default='bibeasy_out',
        help="The label that each output file should have prepended to its name. "
             "For example, '-f docx -l test' could produce a file with the name 'test.docx'."
    )

    # Filtering arguments
    filter_args = parser.add_argument_group(
        "Filtering", "Optional arguments which will filter the citations placed in the output in some way")
    filter_args.add_argument(
        "--year", type=int,
        help="The minimum year (inclusive) that should be kept in the outputs."
    )
    filter_args.add_argument(
        "--type", dest="type_filter",
        help="What types of article (as determined by the name of the subsheets in the document) to preserve"
    )
    filter_args.add_argument(
        "--filters", dest="sql_filters", nargs='*',
        help="A list of SQL-query like filters to apply to the data before outputting the results. "
             "See 'pandas.DataFrame.query:expr' for further details on what filters are allowed."
    )

    # Formatting arguments
    format_args = parser.add_argument_group(
        "Formatting", "Optional arguments that determine how the results will be formatted"
    )
    format_args.add_argument(
        "--style", choices=['APA', 'custom', 'talk'], default='APA',
        help="The citation style to use. Is ignored if the output format has a required citation style (i.e. CCV)."
    )
    format_args.add_argument(
        "--valid_labels", type=Path,
        help="A file containing the list of labels which can be used to group the NeuroPoly publications. "
             "Only used when `--format` is `neuro_md`, ignored otherwise."
    )
    format_args.add_argument(
        "--reverse", action='store_true',
        help="Reverse the order (by year) the bibliography is output in"
    )
    format_args.add_argument(
        "--keep_separate", action='store_true',
        help="Forces the output to be split into multiple files, one per publication type "
             "(sub-sheet in the original input)"
    )

    other_args = parser.add_argument_group(
        "Other", "Miscellaneous other arguments for various utilities"
    )
    other_args.add_argument(
        "--verbose", action='store_true',
        help="When used, MUCH more detail on the underlying processes of the code are displayed"
    )
    other_args.add_argument(
        "--required_columns", nargs='*', default=['Title', 'Authors'],
        help="A list of columns that are required to be non-null in the input set; if an entry is found "
             "to be null in any of these columns, it will be ignored (not placed in the resulting output "
             "file(s))"
    )

    # Pares the arguments and return them
    argvs = parser.parse_args().__dict__
    return argvs


def main(
        input_excel: Optional[pd.ExcelFile], output_format: str, output_path: Path, out_label: str,
        year: Optional[int], type_filter: list[str], sql_filters: list[str], style: str, valid_labels: Optional[Path],
        required_columns: list[str], keep_separate=False, verbose=False, reverse=False, **kwargs
):
    # Set up pretty colored logs
    if verbose:
        coloredlogs.install(fmt='%(message)s', level='DEBUG')
    else:
        coloredlogs.install(fmt='%(message)s', level='INFO')

    # Load the GSheet into a dataframe for ease of use, loading only those that were requested
    df: pd.DataFrame = bibeasy.utils.excel_to_df(input_excel, type_filter)

    # Apply our SQL-like filters first, at they are most likely to reduce the dataframe the most
    if sql_filters is not None:
        for sub_filter in sql_filters:
            df = df.query(sub_filter)

    # Filter by year, if the user requested it
    if year is not None:
        df = df.loc[df['Year'] >= year, :]

    # Remove entries in the dataframe which lack the columns designated as "required" by the user
    df = df.dropna(axis=0, subset=required_columns)

    # Fetch the function to parse the DataFrame's contents to the requested format
    format_func = FORMAT_CALLS[output_format]

    # If the user requested the data be reversed, sort in descending order
    if reverse:
        df = df.sort_values(by='Year', ascending=False)
    # Otherwise, sort in ascending order (the "standard")
    else:
        df = df.sort_values(by='Year', ascending=True)

    # Bundle the keyword-args that might be needed by the formatting function together
    format_kwargs = {
        "style": style,
        "valid_labels": valid_labels
    }

    # If the user requested the result be split, iteratively generate the outputs
    if keep_separate:
        for p in set(df['Type']):
            out_file = output_path / f"{out_label}__{p}.{output_format}"
            out_df = df.loc[df['Type'] == p, :].drop(columns=['Type'])
            format_func(out_df, out_file, **format_kwargs)
    # Otherwise, just output everything into a single file
    else:
        out_file = output_path / f"{out_label}.{output_format}"
        out_df = df.drop(columns=['Type'])
        format_func(out_df, out_file, **format_kwargs)

# == Command Line Interface == #
def cli_hook():
    # SetupTools hook for CLI calls
    cli_args = parse_cli_arguments()
    main(**cli_args)


# If this script is run from a CLI, parse CLI arguments before proceeding
if __name__ == '__main__':
    # Despite SetupTool's docs saying this is valid hook, it isn't, hence the function call hook being used instead
    cli_hook()
