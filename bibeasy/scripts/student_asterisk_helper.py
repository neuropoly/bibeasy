'''
USAGE:
- Export the latest CCV always, keep the old xml around until you confirm the modifications work
- Run it through the script (bibeasy/scripts/student_asterisk_helper.py -i [ccv.xml] -o [ccv-modified.xml]) under a bibeasy virtualenv
- Revert the database with the old xml on CCV-CVC.ca if any error occurs (and of course let me know so I can fix it)

TESTING:
--append can add a single name (ie. Cohen-Adad) for testing with another dataset
this is useful because we're currently stumped on how to import CCV-98720.xml into another account for testing
As such, we've been generating a much smaller dataset within a separate account and testing the xml modifications there
'''

import xml.etree.ElementTree as ET
from bibeasy.formatting import STUDENTS
import argparse

parser = argparse.ArgumentParser(description='Add an asterisk in a CCV xml beside all of Julien\'s students (bibeasy.formatting.STUDENTS)', epilog='see USAGE section in this file for further help')
parser.add_argument('-i', '--input_xml', help='Input CCV xml filename', required=True)
parser.add_argument('-o', '--output_xml', help='Output CCV xml filename (created)', required=True)
parser.add_argument('-a', '--append_name', help='Append name to STUDENTS list (for testing)', required=False)
args = parser.parse_args()

input_name = args.input_xml
output_name = args.output_xml
if args.append_name:
    STUDENTS.append(args.append_name)
    print(STUDENTS)


# Load the data into an XML ElementTree
tree = ET.parse(input_name,  parser=ET.XMLParser(encoding='utf-8'))

# Update the author list
def update_author_list(xml_element):
    # If the element is empty, or has no contents, just return without modification
    if xml_element is None or xml_element.text is None:
        return

    # Contains a list of all author names which were comma-separated, stripped of any padding spaces
    students = [x.strip() for x in xml_element.text.split(',')]

    # remove existing asterisks in student names
    students = [x.replace('*', '') for x in students]
    
    # Process student names, adding asterisks for matches
    students_processed = [x + '*' if x in STUDENTS else x for x in students]

    # NOTE: spacing between names in source xml differs, so it likely is irrelevent
    xml_element.text = ', '.join(students_processed)

# Track the last values element we saw; we will be updating this later

value_cache = None

# Iterate through all cells in the XML tree

for elem in tree.iter():

    # Save the element pointer if it's a value pointer; we won't know what to do with it until we find a field element

    if elem.tag == 'value':

        elem_cache = elem

    elif elem.tag == 'field':

        # Skip early if this tag is

        if not elem.get('label', '') in ['Authors', 'Editors']:

            continue

        update_author_list(elem_cache)

# Pretty-print the xml
# NOTE: this is perfectly valid for CCV-CVC so we're going to leave it here
ET.indent(tree, space='  ')

tree.write(output_name, encoding='utf-8')


