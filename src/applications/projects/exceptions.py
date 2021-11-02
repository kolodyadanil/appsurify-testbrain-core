# -*- coding: utf-8 -*-


class ProjectOwnershipRequired(Exception):
    """
    Exception to raise if the owner is being removed before the
    project.
    """
    pass


class ProjectMismatch(Exception):
    """
    Exception to raise if an project user from a different
    project is assigned to be an project's owner.
    """
    pass


class ProjectOwnerAlreadyExists(Exception):
    """
    Exception to raise if an project user from a different
    project is assigned to be an project's owner.
    """
    pass
