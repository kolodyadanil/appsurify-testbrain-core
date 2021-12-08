# -*- coding: utf-8 -*-

"""
from P4 import P4, P4Exception
p4 = P4()
p4.port = "public.perforce.com:1666"
p4.user = "james"
p4.password = "Password!"
p4.client = "james_ws"
p4.connect()
"""

"""
    -f //guest/perforce_software/p4jenkins - branch
     = depot
    stream = branch
    change = commit

"""


"""
git config git-p4.user james
git config git-p4.password Password!
git config git-p4.client james_ws
git config git-p4.host public.perforce.com
git config git-p4.port public.perforce.com:1666

git p4 clone //guest/perforce_software/p4jenkins/main@all .
импортирует историю коммитов

git p4 clone --detect-branches //guest/perforce_software/p4jenkins@all .
импортирует историю + ветви


git p4 sync --branch=refs/remotes/p4/main //guest/perforce_software/p4jenkins/main
импортирует 1 коммит как инициализирующий

git p4 sync --branch=refs/remotes/p4/main //guest/perforce_software/p4jenkins/main@all      
Import destination: refs/remotes/p4/main
Importing revision 26204 (100%)
fast-import failed: warning: Not updating refs/remotes/p4/main (new tip dac1872059380eab3fc006a9ffd4df1c9ac5792b does not contain 5e748e0bfd655a155a8f17308c8bac16cdee1c08)
/usr/local/git/libexec/git-core/git-fast-import statistics:
---------------------------------------------------------------------
Alloc'd objects:      15000
Total objects:        10779 (       678 duplicates                  )
      blobs  :         2264 (       527 duplicates       1640 deltas of       2262 attempts)
      trees  :         7651 (       151 duplicates       3458 deltas of       7475 attempts)
      commits:          864 (         0 duplicates          0 deltas of          0 attempts)
      tags   :            0 (         0 duplicates          0 deltas of          0 attempts)
Total branches:           1 (         1 loads     )
      marks:        1048576 (       864 unique    )
      atoms:            516
Memory total:          3071 KiB
       pools:          2133 KiB
     objects:           937 KiB
---------------------------------------------------------------------
pack_report: getpagesize()            =       4096
pack_report: core.packedGitWindowSize = 1073741824
pack_report: core.packedGitLimit      = 35184372088832
pack_report: pack_used_ctr            =        867
pack_report: pack_mmap_calls          =          2
pack_report: pack_open_windows        =          2 /          2
pack_report: pack_mapped              =   81658598 /   81658598
---------------------------------------------------------------------
git log --pretty="%h - %s"                                                            
5e748e0 - Initial import of //guest/perforce_software/p4jenkins/main/ from the state at revision #head



"""