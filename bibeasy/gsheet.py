#!/usr/bin/env python
#
# Communication with GoogleSheet API


import sys
import os
import xdg.BaseDirectory
import requests
import pandas
import logging
import numpy as np

import bibeasy

# this spreadsheet records neuro.polymtl.ca's publications; it must be Public.
PUBLICATIONS = "https://docs.google.com/spreadsheets/d/1dEUBYf17hNM22dqV4zx1gsh3Q-d97STnRB4q7p9nQ54"

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

    logging.info(f"Fetching GoogleSheet '{PUBLICATIONS}'...")
    gsheet = requests.get(f'{PUBLICATIONS}/export?format=xlsx')
    gsheet.raise_for_status()

    # cache result
    cache = xdg.BaseDirectory.save_cache_path('bibeasy')
    publications = os.path.join(cache, "publications.xlsx")
    with open(publications, "wb") as fd:
        fd.write(gsheet.content)


def fetch_gsheet_contents(pubtypes):
    """
    Fetch publication records from GoogleSheet API
    :param pubtypes: list: Can contain the following items: {'article', 'proceedings'}.
    :return: Pandas dataframe
    """

    cache = xdg.BaseDirectory.save_cache_path('bibeasy')
    publications = os.path.join(cache, "publications.xlsx")
    if not os.path.exists(publications):
        fetch_gsheet_from_the_web()

    publications = pandas.read_excel(publications,
                                     engine='openpyxl',
                                     sheet_name=list(pubtypes)) # when sheet_name is a list, gives
                                                                # a dict keyed by its contents
                                                                # and greatly speeds up parsing.
    # union the multiple sheets into a single DataFrame
    pub_lst = []
    for pubtype, df_pubs in publications.items():
        df_pubs['Type'] = pubtype
        pub_lst.append(df_pubs)
        logging.info(f"  Total '{pubtype}' entries: {len(df_pubs)}")
    df_tmp = pandas.concat(pub_lst, ignore_index=True)
    return df_tmp


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

    df_csv = fetch_gsheet_contents(args.type)

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
