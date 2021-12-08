from applications.project.models import Project
from applications.testing.utils.prediction.output.additional_model import additional_output_model_analyzer
from applications.testing.utils.prediction.output.initial_model import initial_output_model_analyzer


def output_analyze(project_id, commits_hashes=None):
    project = Project.objects.filter(id=project_id).last()

    if not project:
        return False

    if project.defects.count() >= 20:
        result = additional_output_model_analyzer(project_id=project.id, commits_hashes=commits_hashes)
    else:
        result = initial_output_model_analyzer(project_id=project.id, commits_hashes=commits_hashes)

    return result
