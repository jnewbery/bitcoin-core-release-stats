#!/usr/bin/env python3
"""Get Release Stats

Get statistics for different Bitcoin Core releases."""
from collections import defaultdict
import configparser
import csv
import json
import os
import requests
import subprocess

class Github():
    # Handles requests to the github API

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

    def request(self, req):
        """makes request to the github API."""
        return json.loads(requests.get('https://api.github.com/{}?client_id={}&client_secret={}'.format(req, self.client_id, self.client_secret)).text)

def main():

    # Read config file
    config = configparser.ConfigParser()
    configfile = os.path.abspath(os.path.dirname(__file__)) + "/config.ini"
    config.read_file(open(configfile, encoding="utf8"))

    bitcoin_dir = config["DEFAULT"]["bitcoin_directory"]

    for release in config.sections():
        # Each non-default section in the config file is a new release
        prev_branch = config[release]["previous_branch"]
        branch = config[release]["branch"]

        # Get number of non-merge commits in this release
        commits_cmd = "git -C {} -P log {}..{} --oneline --no-merges | wc -l".format(bitcoin_dir, prev_branch, branch)
        commits = subprocess.run(commits_cmd, shell=True, universal_newlines=True, stdout=subprocess.PIPE).stdout.rstrip("\n")

        # Get number of PRs merged in the release.
        # This is highly dependent on the log message format. TODO: Improve this by using the github API to find out when PRs were merged to master
        merges_cmd = "git -C {} -P log {}..{} --oneline | grep \"Merge #\" | grep -v \"Revert \\\"Merge\" | cut -f 3 -d \" \" | cut -c 2- | cut -f 1 -d \":\" | sort -n | wc -l".format(bitcoin_dir, prev_branch, branch)
        merges = subprocess.run(merges_cmd, shell=True, universal_newlines=True, stdout=subprocess.PIPE).stdout.rstrip("\n")

        # Get commit authors
        authors = set()
        authors_cmd = "git -C {} log {}..{} --no-merges --pretty=format:\"%an\" | sort | uniq".format(bitcoin_dir, prev_branch, branch)
        authors = set([a for a in subprocess.run(authors_cmd, shell=True, universal_newlines=True, stdout=subprocess.PIPE).stdout.splitlines()])
        merge_base = subprocess.run("git -C {} merge-base master {}".format(bitcoin_dir, prev_branch), shell=True, universal_newlines=True, stdout=subprocess.PIPE).stdout.rstrip("\n")
        old_authors_cmd = "git -C {} log {} --no-merges --pretty=format:\"%an\" | sort | uniq".format(bitcoin_dir, merge_base)
        old_authors = set([a for a in subprocess.run(old_authors_cmd, shell=True, universal_newlines=True, stdout=subprocess.PIPE).stdout.splitlines()])

        num_new_authors = len(authors.difference(old_authors))

        print("Version {} had {} commits from {} authors ({} new) and {} merges".format(release, commits, len(authors), num_new_authors, merges))

        authors_by_commit_cmd = "git -C {} log {}..{} --no-merges --pretty=format:\"%an\" | sort | uniq -c | sort -n -r".format(bitcoin_dir, prev_branch, branch)
        authors_by_commit = subprocess.run(authors_by_commit_cmd, shell=True, universal_newlines=True, stdout=subprocess.PIPE).stdout.splitlines()[0:10]

        print("Most prolific committers:\n {}".format("\n".join(authors_by_commit)))

    gh = Github(config["DEFAULT"]["client_id"], config["DEFAULT"]["client_secret"])

    contributors = defaultdict(int)
    pulls = []
    # Read PRs merged in this release
    with open('PRs_15.txt', 'r', encoding='utf-8') as f:
        for l in f:
            pulls.append(l.rstrip())

    # Check our Github API rate limit
    rate_limit = gh.request('rate_limit')
    print(rate_limit)

    for pr in pulls:
        print("PR {}".format(pr))
        # Get PR comments and review comments
        pr_comments = gh.request('repos/bitcoin/bitcoin/issues/{}/comments'.format(pr))
        review_comments = gh.request('repos/bitcoin/bitcoin/pulls/{}/comments'.format(pr))
        if pr_comments:
            print("{} pr comments for {}".format(len(pr_comments), pr))
            for comment in pr_comments:
                contributors[comment['user']['login']] += 1
        else:
            print("no pr comments for {}".format(pr))
        if review_comments:
            print("{} review comments for {}".format(len(review_comments), pr))
            for comment in review_comments:
                if comment['user'] is not None:
                    contributors[comment['user']['login']] += 1
        else:
            print("no review comments for {}".format(pr))

    print(contributors)

    # Write reviewers/contributors to an output file
    with open('commenters_15.csv', 'w', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['commenter', 'comments'])
        for contributor in contributors:
            writer.writerow([contributor, contributors[contributor]])

if __name__ == '__main__':
    main()
