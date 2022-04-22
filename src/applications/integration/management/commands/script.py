# -*- coding: utf-8 -*-

import requests
import sys
import json
import os
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from applications.project.models import Project
from applications.integration.github.models import GithubRepository
from applications.vcs.models import Branch, Commit, ParentCommit
from django.core.management.base import BaseCommand
from django.db import transaction, connection
import datetime

GITHUB_API_URL = 'https://api.github.com'
MAX_COMMIT     = 100
NOT_ERROR      = 0
ERROR          = 1
HTTP_SUCCESS   = 200

class Command(BaseCommand):
    help = 'Run script, get all commit in a branch and save to database'

    def add_arguments(self, parser):
        parser.add_argument('--project_id', type = int, help = 'Indicates the number of project to be find')
        parser.add_argument('--commit', type = str, help = 'Define a commit')
        parser.add_argument('--branch', type = str, help = 'Define a branch')
        parser.add_argument('--page', type = int, help = 'Define page for list commit')

    @transaction.atomic()
    def handle(self, *args, **kwargs):
        print('------------Start script-------------')

        try:
            # get repo_owner and repo_name in system
            record = GithubRepository.objects.get( project_id = kwargs['project_id'])
            if not record : raise Exception("Your project is not in system!")

            # open transaction
            tran = transaction.savepoint()
            # set up header and url to call api github and get all commit in branch
            headers = {
                'Authorization': 'token {}'.format(record.token)
            }
            # --------- Start save branch---------
            url_branch = GITHUB_API_URL + '/repos/{}/branches/{}'.format(record.github_repository_name, kwargs['branch'])
            # call api get branch
            response_branch = requests.get(url = url_branch, headers = headers)
            if (response_branch.status_code == HTTP_SUCCESS) :
                response_branch = response_branch.json()
                check_branch    = Branch.objects.filter(project_id = kwargs['project_id'], name = kwargs['branch']).first()
                if not check_branch:
                    save_branch = Branch.objects.create(
                            project_id = kwargs['project_id'], 
                            name = kwargs['branch'], 
                            sha = response_branch['commit']['sha']
                        )
                    id_branch = save_branch.id
                    print('Save VSC_Branch Success !!')
                else : id_branch = check_branch.id

            else : 
                transaction.savepoint_rollback(tran)
                raise Exception("System cannot call to api!")
            # --------- End save branch --------

            # --------------- Start save commit ------------------
            url_commits  = GITHUB_API_URL + '/repos/{}/commits'.format(record.github_repository_name)
            url_a_commit = GITHUB_API_URL + '/repos/{}/commits/{}'.format(record.github_repository_name, kwargs['commit'])
            # param for api get commit 
            parameters = {}
            parameters.update({'per_page': MAX_COMMIT})
            if kwargs['page'] : parameters.update({'page': kwargs['page']})
            if kwargs['branch'] : parameters.update({'sha': kwargs['branch']})

            # call api get commit
            response_a_commit = requests.get(url = url_a_commit, headers = headers)
            response_commits  = requests.get(url = url_commits, headers = headers, params = parameters)
            if (response_commits.status_code == HTTP_SUCCESS) and (response_a_commit.status_code == HTTP_SUCCESS) :
                var = response_commits.json()
                single_commit = response_a_commit.json()
                d1 = datetime.datetime.strptime(single_commit['commit']['committer']['date'],"%Y-%m-%dT%H:%M:%SZ")

                with connection.cursor() as cursor:
                    for x in range(0, len(var)):
                        d2 = datetime.datetime.strptime(var[x]['commit']['committer']['date'],"%Y-%m-%dT%H:%M:%SZ")
                        # compare date with commit in parameter
                        if (d1 >= d2):
                            cursor.execute('''
                                INSERT INTO vcs_commit (
                                    project_id, riskiness, output, 
                                    rework, tree, stats, message, 
                                    committer, author, url, display_id, 
                                    sha, repo_id, timestamp, created, updated)
                                VALUES(%s,0,0,0,%s,%s,%s,%s,%s,%s,%s,%s,%s, current_timestamp, current_timestamp, current_timestamp)
                                    ON CONFLICT (project_id, sha) DO NOTHING returning true
                                    ''',
                                [
                                    kwargs['project_id'],
                                    json.dumps(var[x]['commit']['tree'], indent=4), 
                                    json.dumps(var[x]['commit']['tree'], indent=4), 
                                    var[x]['commit']['message'], 
                                    json.dumps(var[x]['commit']['committer'], indent=4), 
                                    json.dumps(var[x]['author'], indent=4),
                                    var[x]['url'],
                                    var[x]['sha'][:7],
                                    str(var[x]['sha']),
                                    str(var[x]['sha'])
                                ]
                            )
                            # save vcs_commit_brances
                            cursor.execute('''
                                INSERT INTO vcs_commit_branches (
                                    commit_id, branch_id)
                                VALUES(%s,%s)
                                    ON CONFLICT (commit_id, branch_id) DO NOTHING returning true
                                    ''',
                                [
                                    Commit.objects.last().id,
                                    id_branch
                                ]
                            )

                            # save vcs_file table
                            url_a_commit_file = GITHUB_API_URL + '/repos/{}/commits/{}'.format(record.github_repository_name, var[x]['sha'])
                            response_a_commit_file = requests.get(url = url_a_commit_file, headers = headers)
                            file = response_a_commit_file.json()

                            if not response_a_commit_file : raise Exception("System cannot call to api!")
                            if len(file['files']) > 0:
                                cursor.execute('''
                                    INSERT INTO vcs_file (
                                        sha, filename, full_filename, 
                                        raw_url, blob_url, contents_url, lft, 
                                        rght, tree_id, level, project_id, 
                                        created, updated)
                                    VALUES(%s,%s,%s,%s,%s,%s,1,1,1,1,%s, current_timestamp, current_timestamp)
                                        ON CONFLICT (project_id, filename, parent_id) DO NOTHING returning true
                                        ''',
                                    [
                                        file['files'][0]['sha'],
                                        file['files'][0]['filename'].split('/')[-1],
                                        file['files'][0]['filename'],
                                        file['files'][0]['raw_url'],
                                        file['files'][0]['blob_url'],
                                        file['files'][0]['contents_url'],
                                        kwargs['project_id']
                                    ]
                                )

                            # save vcs_parentcommit table
                            commit_current = Commit.objects.filter(sha = file['sha']).first()
                            for y in range(0, len(file['parents'])):
                                commit_parent  = Commit.objects.filter(sha = file['parents'][y]['sha']).first()
                                if commit_parent and commit_current:
                                    ParentCommit.objects.create(index_number = y, from_commit_id = commit_parent.id, to_commit_id = commit_current.id)

                    save = cursor.fetchall()
                    print('Save VSC_File Success !!')
                    print('Save VSC_Commit Success !!')
                    print('Save VSC_ParentCommit Success !!')
            else : 
                transaction.savepoint_rollback(tran)
                raise Exception("System cannot call to api!")
            # --------------- End save commit ------------------
            
            # handle success
            transaction.savepoint_commit(tran)

        except Exception as e:
            transaction.savepoint_rollback(tran)
            print('System cannot save branch and commit!')
            print(e)

        print('------------End script-------------')