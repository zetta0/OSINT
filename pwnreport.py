#!/usr/bin/env python3

"""
This tool queries the haveibeenpwned API to return a list of breached
email addresses.
There are other tools that do the same, maybe better, but I wanted something
that creates an output I can paste directly into a pentest report. Also it
is smart enough to extract valid email addresses anywhere in a text file,
so you don't need to clean anything up first.
Enjoy!
github.com/initstring
"""

import argparse
import time
import re
import os
import sys
import requests


# Global variables for most-likely-to-change items:
#   - API bans may happen at the User-Agent level
#   - API endpoint may change
USER_AGENT = 'pwned_reportv1'
API_URL = 'https://haveibeenpwned.com/api/v3/breachedaccount'


def process_args():
    """Handles user-passed parameters"""
    parser = argparse.ArgumentParser(description='Check haveibeenpwned for'
                                     ' compromised email addresses.')

    parser.add_argument('-a', '--apikey', required=True, type=str,
                        help='HIBP API key')    
    parser.add_argument('-f', '--infile', required=True, type=str,
                        help='Text file with email addresses, formatted'
                        ' anyway you like.')
    parser.add_argument('-s', '--sleep', default=1.6, type=int,
                        help='Seconds to sleep between each email. Default'
                        ' is 1.6 seconds.')
    parser.add_argument('-o', '--outfile', default='pwned.txt', type=str,
                        help='Log file to write output to. Default is'
                        ' pwned.txt')

    args = parser.parse_args()

    if not os.access(args.infile, os.R_OK):
        print("[!] Cannot access input file, please try again.")
        sys.exit()

    return args


def find_emails(infile):
    """
    Uses a regex to extract all email address from an input file.
    """
    # Thanks to regular-expressions.info for this regex
    regex = r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}'

    # Read the file into a string, extract vaid emails
    print("[+] Processing {}".format(infile))
    with open(infile) as file_handler:
        raw_text = file_handler.read()
        emails = re.findall(regex, raw_text, re.IGNORECASE)

    if not emails:
        print("[!] No valid emails found, exiting.")
        sys.exit()

    print("[+] Found {} valid email addresses in {}"
          .format(len(emails), infile))

    return emails


def collect_results(emails, sleep_time, apikey):
    """
    Grabs the raw, truncated, results from the API.
    """
    # API demands a custom header, so we set it here
    headers = {'User-Agent': USER_AGENT,'hibp-api-key': apikey}

    # Initialize a dictionary for all the results
    results = {}

    # Start a counter for failed responses
    failed_count = 0

    # Start a counter for the status bar
    total_count = 1

    # Initiate a session to maintain cloudflare cookies, hopefully to
    # avoid rate limiting
    sess = requests.session()

    for address in emails:
        # 'truncated' URL param required for proper parsing
        url = API_URL + '/{}?truncateResponse=true'.format(address)

        # Quick and dirty status counter
        sys.stdout.write('\r')
        sys.stdout.write("[+] Checking {} out of {}"
                         .format(total_count, len(emails)))

        # Get the results
        res = sess.get(url, headers=headers)

        # Update status bar with HTTP resonse code
        sys.stdout.write("    |    HTTP Status: {}"
                         .format(res.status_code))

        # We expect a 200 or 404 - otherwise, might be rate limited
        if res.status_code != 200 and res.status_code != 404:
            failed_count += 1
            if failed_count >= 3:
                print("")
                print("[!] Possible rate limiting encountered.")
                sys.exit()

        # A response with text means breaches found. Add to dictionary.
        if res.text:
            results[address] = res.text

        # Increment the counter and flush stdout
        total_count += 1
        sys.stdout.flush()

        # Sleep to avoid rate limiting
        time.sleep(sleep_time)

    print("") # Need a new line after using sys.stdout to display counter
    print("[+] Found {} accounts with breach data".format(len(results)))
    return results


def format_results(results):
    """
    Outputs the breach data via markdown, ready to paste into a report.
    """
    # Initialize a new dictionary of known breach names
    known_breaches = {}

    # Breaches are returned in JSON-like format
    regex = '"Name":"(.*?)"'

    # Loop through our results, building the new dictionary ordered
    # by breach name instead of account name
    for address in results:
        breaches = re.findall(regex, results[address], re.IGNORECASE)
        for breach in breaches:
            if breach in known_breaches:
                known_breaches[breach].append(address)
            else:
                known_breaches[breach] = [address,]

    return known_breaches


def deliver_results(results, outfile):
    """
    Write final results to log file.
    """
    print("[+] Writing results to {}".format(outfile))
    with open(outfile, 'w') as file_handler:
        for breach in results:
            file_handler.write('**{}**\n'.format(breach))
            for email in results[breach]:
                file_handler.write('* {}\n'.format(email))
            file_handler.write('\n')

    print("[+] All done, enjoy!")


def main():
    """
    Main program function.
    """
    args = process_args()
    emails = find_emails(args.infile)
    raw_results = collect_results(emails, args.sleep, args.apikey)
    final_results = format_results(raw_results)
    deliver_results(final_results, args.outfile)


if __name__ == '__main__':
    main()
