#!/usr/bin/env python
"""Convert Schwab EAC 1099 PDF to TurboTax TXF and CSV format. No need to copy-paste."""

# TXF spec: http://turbotax.intuit.com/txf/TXF042.jsp

import csv
import re
import subprocess
import sys
from datetime import date

class Record:
  def __init__(self):
    self.fields = []
  def addField(self, op, val):
    self.fields.append((op, val))
  def writeRecord(self, output):
    for f in self.fields:
      output.write("%s%s\n" % f)
    output.write ("^\n")

len(sys.argv) == 3 or sys.exit("Syntax: %s <input file> <output file>" % sys.argv[0])

input_fn = sys.argv[1]
output_fn = sys.argv[2]

#with open(input_fn, 'r') as f:
#  lines = [l.strip() for l in f.readlines()]
lines = [l.strip() for l in subprocess.check_output(['pdftotext', '-raw', input_fn, '-'], universal_newlines=True).split('\n')]

output = open(output_fn + '.txf', 'w')
output_csv = open(output_fn + '.csv', 'w')

# Write out the TXF header
header = Record()
header.addField('V', '042')
header.addField('A', 'JBeda\s quick and dirty TXF script')
header.addField('D', date.today().strftime('%m/%d/%Y'))
header.writeRecord(output)

csv_writer = csv.writer(output_csv)
csv_writer.writerow(['Symbol', 'Quantity', 'Date Acquired', 'Date Sold', 'Cost Basis', 'Sales Proceeds', 'Wash', 'Adjustment'])

input_line = 0
total_proceeds = 0
total_basis = 0
total_wash = 0
while True:
  # Pop 4 lines off the top of the input file.  It will look something like this:
  # 38259P508
  # 2 SHARES OF GOOG
  # 09/19/2012 1,352.17 1,565.62 <W> X
  # 11/28/2012 Gross <92.56>
  #
  # These fields are:
  # <CUSIP Number>
  # <Num> SHARES OF GOOG/GOOGL
  # <Acquisition Date> <Net proceeds> <Cost or other basis> <wash sale disallowed>? <non-covered security>
  # <Sale Date> Gross <Wash sale disallowed amount>?

  if len(lines) == input_line:
    break

  if len(lines) < input_line + 4:
    #print 'WARNING: Trailing content at end of file: \n%s' % repr(lines[input_line:])
    break

  if (not lines[input_line].startswith('3825') and not lines[input_line].startswith('0207')):
    input_line += 1
    continue

  cuspid = lines[input_line]

  input_line += 1
  parts = lines[input_line].split(' ')

  if len(parts) != 4 or parts[1] != 'SHARES' or parts[2] != 'OF':
    sys.exit('ERROR: Parsing input line %d: %s' % (input_line+1, lines[input_line]))
  quantity = float(parts[0])

  symbol = parts[3]
  if (symbol != 'GOOG' and symbol != 'GOOGL') or quantity <= 0.0:
    sys.exit('ERROR: Parsing input line %d: %s' % (input_line+1, lines[input_line]))

  input_line += 1
  parts = lines[input_line].split(' ')
  len(parts) == 4 or sys.exit('ERROR: Parsing input line %d: %s' % (input_line+1, lines[input_line]))
  wash = ''
  (acq_date, proceeds, basis, non_covered) = parts

  # Strip out commas and quotation marks
  proceeds = re.sub('[\",]', '', proceeds)
  basis = re.sub('[\",]', '', basis)

  if non_covered != 'X':
    sys.exit('ERROR: Line %d. Expected to see X but instead saw: \n%s' % (input_line+1, lines[input_line]))


  # In the 2016 return the parser returns sale date, wash sale disallowed and
  # the 'GROSS' field on separate lines. But sometimes they can be on the same
  # line. I know. Confusing.
  input_line += 1
  parts = lines[input_line].split()
  if len(parts) > 1: # Sale Date and 'GROSS' are on the same line
    sale_date = parts[0]
    wash = '' # No Wash sale
  else:
    sale_date = lines[input_line]
    input_line += 1
    if lines[input_line] != 'GROSS':
      wash = lines[input_line]
      input_line += 1
    else:
      wash = ''

  input_line += 1

  total_proceeds += float(proceeds.replace(',', ''))
  total_basis += float(basis.replace(',', ''))
  if wash:
    total_wash += float(wash.replace(',', ''))

  # A TXF record here looks like:
  # TD            Detailed Record
  # N715          Refnumber
  # C1            Copy number
  # L1            Line number
  # P50 QCOM      Description
  # D01/02/2010   Date acquired
  # D01/15/2011   Date sold
  # $1500         Cost Basis
  # $1300         Sales Net
  # $200          Disallowed wash sale amount
  # ^
  item = Record()
  item.addField('T', 'D')
  item.addField('N', '715')
  item.addField('C', '1')
  item.addField('L', '1')
  item.addField('P', '%s %s' % (quantity, symbol))
  item.addField('D', acq_date)
  item.addField('D', sale_date)
  item.addField('$', basis)
  item.addField('$', proceeds)
  item.addField('$', wash)
  item.writeRecord(output)

  csv_writer.writerow([symbol, quantity, acq_date, sale_date, basis, proceeds, 'W' if wash!='' else '', wash])

print "Verify these totals with the summary of the last page of the Schwab Statement"
print "Total Proceeds: $%.2f" % total_proceeds
print "Total Basis: $%.2f" % total_basis
print "Total Wash: $%.2f" % total_wash
