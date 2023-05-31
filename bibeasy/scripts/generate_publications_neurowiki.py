# encoding="utf-8"
# 1. You have to download the Gsheet publications in csv format
# 2. Run script by indicating the path to the csv file
# Developed by: Alexandru Foias
# 2018-11-1

import csv
import argparse
import os
import re

def get_parameters():
    parser = argparse.ArgumentParser(description='This script is used for'
        'generating the publications content for neurowiki')
    parser.add_argument("-c", "--csv",
                        help="Path to csv containing publications",
                        required=True)
    args = parser.parse_args()
    return args

def main(path_csv):
    """
    Main function
    :param path_csv:
    :return:
    """
        # Read csv file
    file_csv = open(path_csv, 'rb')
    reader_csv = csv.reader(file_csv)
    buffer_csv = []
    for row in reader_csv:
        buffer_csv.append(row)
    file_csv.close()

    list_csv_title = []
    list_csv_author = []
    list_csv_journal_name = []
    list_csv_journal_info = []
    list_csv_URL = []

    for hh in range(1, len(buffer_csv)):  # we skip the first row (contains header)
        csv_author = buffer_csv[hh][1].split('. ')[0] #strip author assuming that is delimited by period
        csv_title = buffer_csv[hh][1].split('. ')[1] #strip author assuming that is delimited by period
        if len(buffer_csv[hh][1].split('. ')) < 3: #dealiming with titles ending in ?
            csv_title = (csv_title.split('? ')[0]) + '?'
        csv_journal = buffer_csv[hh][1].split('. ')[2:]
        csv_journal = ' '.join(csv_journal)
        csv_journal_name = re.split(r'(\d+)',csv_journal) #strip journal name assuming that the name ends at the first numeric value
        if len(csv_journal_name) > 1: # grab journal information year,doi etc.
            csv_journal_info = csv_journal.split(csv_journal_name[0])
            csv_journal_info = ''.join(csv_journal_info)
        else:
            csv_journal_info = '' # generate void content if journal information year,doi etc. doesn't exist
            
        list_csv_URL.append(buffer_csv[hh][7])
        list_csv_title.append(csv_title)
        list_csv_author.append(csv_author)
        list_csv_journal_name.append(csv_journal_name[0])
        list_csv_journal_info.append(csv_journal_info)

    list_output_txt = [] #generate text format for https://www.neuro.polymtl.ca/publications#journal_articles respecting dokuwiki formatting parameters
    for row_id in reversed (range(len(list_csv_author))):
        list_output_txt.append('   - ' +  list_csv_author[row_id] + '. [[' + list_csv_URL[row_id] + '|' + list_csv_title[row_id] + ']] ' + '**' + list_csv_journal_name[row_id] + '** ' + list_csv_journal_info[row_id])

    buffer_root_path_output_csv = path_csv.split('/') # generate path for output file; saved in the same location as the csv file
    root_path_output_csv = '/'.join(str(buffer_root_path_output_csv[i]) for i in range (len(buffer_root_path_output_csv)-1))

    with open(root_path_output_csv + '/content_publications_neurowiki.txt', 'w') as txtFile: #write new generated publications in txt file
        for item in list_output_txt:
            txtFile.write("%s\n" % item)
    txtFile.close()

if __name__ == "__main__":
    args = get_parameters()
    main(args.csv)
