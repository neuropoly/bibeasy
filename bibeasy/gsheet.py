#!/usr/bin/env python
#
# Communication with GoogleSheet API

import logging
from pathlib import Path

import numpy as np
import pandas
import pandas as pd
import requests
import xdg.BaseDirectory

# URL to the spreadsheet records for neuro.polymtl.ca's publications; this must be Public to be accessed w/ xdg.
PUBLICATION_URL = "https://docs.google.com/spreadsheets/d/1dEUBYf17hNM22dqV4zx1gsh3Q-d97STnRB4q7p9nQ54"

# The XDG cache path to store everything in
CACHE_PATH = Path(xdg.BaseDirectory.save_cache_path('bibeasy'))
DATA_XLSX = CACHE_PATH / "publications.xlsx"

def _dropna_if_field_exists(df, fields):
    """
    Drop rows with nan in specified fields. Check if fields exists before dropping.
    :param df:
    :param fields:
    :return:
    """
    for field in fields:
        if field in df:
            df = df.dropna(subset=[field])
    return df


def fetch_gsheet_from_the_web():
    """
    Fetch publication records from GoogleSheet API
    """
    # Pull the results from the Google sheet
    logging.info(f"Fetching GoogleSheet '{PUBLICATION_URL}'...")
    # Import the data stream in xlsx format; unfortunately we can't use TSV, as this sheet has multiple sub-sheets...
    gsheet = requests.get(f'{PUBLICATION_URL}/export?format=xlsx')
    gsheet.raise_for_status()

    # Save the contents of the Google sheet to a cached file
    with open(DATA_XLSX, "wb") as fd:
        fd.write(gsheet.content)


def load_gsheet_contents(pub_types):
    """
    Fetch publication records from GoogleSheet API
    :param pub_types: The subset of publication types (sub-sheets) you want to grab from the Google Sheet cache
    :return: Pandas dataframe
    """
    if not DATA_XLSX.exists():
        fetch_gsheet_from_the_web()

    # The ExcelFile interface keeps the sub-sheets bundled nicely for us, without needing to explicitly define
    #  the sub-sheet labels.
    xlsx_file = pandas.ExcelFile(DATA_XLSX)

    # If the user didn't explicitly request a subset of publication types, use all of them
    if len(pub_types) < 1:
        pub_types = xlsx_file.sheet_names
    # Otherwise, check if any sheets requested by the user are not present, and raise an error if any are found
    else:
        invalid_types = set(pub_types) - set(xlsx_file.sheet_names)
        if len(invalid_types) > 0:
            raise ValueError(
                f"Requested publication types '{invalid_types}' which do not exist in the cache. "
                f"Valid publication types are '{set(xlsx_file.sheet_names)}'. "
                f"Check for typos, and confirm that the cache is up-to-date!"
            )

    # Iterate through the requested sheets, preparing them to be concatenated
    sub_dfs = []
    for sub_sheet_id in pub_types:
        # Read the sub-sheet DataFrame
        sub_df = pd.read_excel(xlsx_file, sub_sheet_id)

        # Set the 'type' of the sub_df to the sheet's name
        sub_df['Type'] = sub_sheet_id

        # Store the result in a list to be stacked later
        sub_dfs.append(sub_df)

        # Log the size of the result for the user
        logging.info(f"\tTotal '{sub_sheet_id}' entries: {sub_df.shape[0]}")

    # Concatenate them all together into one full dataframe
    return_df = pandas.concat(sub_dfs, ignore_index=True)
    return return_df


def check_labels(df, label_location):
    """
    Check if labels are correct.
    :param df:
    :return:
    """
    logging.info("Checking labels...")
    # Fetch authorized label values
    with open(label_location, "r") as f:
        authorized_labels = [line.strip() for line in f]

    # Define a function to check if a label is authorized
    def is_authorized(label):
        return label.strip() in authorized_labels

    # Check if the "Labels" column exists in the DataFrame
    if "Labels" in df.columns:
        # Check if all labels are authorized
        authorized_mask = df["Labels"].apply(lambda x: all(is_authorized(label) for label in x.split(",")))
        if not authorized_mask.all():
            # Create a new DataFrame with the unauthorized rows
            unauthorized_df = df.loc[~authorized_mask, ["ID", "Labels"]]
            unauthorized_df["Invalid Labels"] = unauthorized_df["Labels"].apply(
                lambda x: ", ".join(label.strip() for label in x.split(",") if not is_authorized(label)))
            unauthorized_df.drop("Labels", axis=1, inplace=True)
            # Raise an error with the unauthorized rows
            raise ValueError(f"Invalid labels found:\n{unauthorized_df.to_string(index=False)}")
    else:
        # If the "Labels" column doesn't exist, create a new "Authorized" column with False values
        df["Authorized"] = False


def gsheet_to_df(args):
    """
    Fetch GoogleSheet list of publications, convert to Pandas DF and filter based on user arguments.
    :param args:
    :return:
    """
    if args.freshen_cache:
        fetch_gsheet_from_the_web()

    df_csv = load_gsheet_contents(args.type)

    # Remove rows with empty fields (those that contain NaN)
    df_csv = df_csv.replace('', np.nan, regex=True)
    df_csv = _dropna_if_field_exists(df_csv, ['Title', 'Year', 'Journal/Conference'])

    # Replace all nans by empty string
    df_csv = df_csv.replace(np.nan, '', regex=True)

    # Check if labels are correct
    if args.check_labels:
        check_labels(df_csv, args.labels)

    # Fix data types
    df_csv.Year = df_csv.Year.astype(int)

    # Filter by tag
    if args.filter:
        df_csv = df_csv[df_csv[args.filter] == 'x']

    # Filter by minimum year
    if args.min_year:
        df_csv = df_csv[df_csv['Year'].astype(int) >= args.min_year]

    # Reverse sorting
    if args.reverse:
        df_csv = df_csv.iloc[::-1]

    return df_csv
