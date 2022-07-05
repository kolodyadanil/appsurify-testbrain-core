import logging

from applications.ml.network import FastCommitRiskinessRFCM
from applications.vcs.models import Commit


def fast_model_analyzer(project_id, commits_hashes=None):
    logging.debug(f"Begin analyze for project: {project_id}")
    try:
        fcr_rfcm = FastCommitRiskinessRFCM(project_id=project_id)
        fcr_rfcm = fcr_rfcm.train()

        riskiness_commits = fcr_rfcm.predict_to_riskiness(commit_sha_list=commits_hashes)

        for sha, riskiness in riskiness_commits.items():
            Commit.objects.filter(sha=sha).update(riskiness=riskiness)

    except Exception as exc:
        logging.exception(f"Some error for fast model analyzer")
        raise exc
