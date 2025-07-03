from github import Github, UnknownObjectException
from github.AuthenticatedUser import AuthenticatedUser
from pydantic import BaseModel

from typing import Tuple
import os
import logging
import yaml

logging.basicConfig(level=logging.INFO)


class Project(BaseModel):
    repos: list[str]
    maintainers: list[str]


class Auth:
    def __init__(self, GITHUB_TOKEN):
        self.github = Github(GITHUB_TOKEN)
        self.org = self.github.get_organization("SDC-MUJ")

    def update_project(self, project: Project, internal_team: list[str]) -> None:
        for repo_meta in project.repos:
            try:
                repo = self.org.get_repo(repo_meta)
            except UnknownObjectException:
                # Create repo if not exist
                logging.warning(f"Repo {repo_meta} does not exist. Creating ...")
                repo = self.org.create_repo(name=repo_meta, private=True)

            collaborators: set[str] = {
                user.login.lower() for user in repo.get_collaborators()
            }
            logging.debug(f"Current collaborators for {repo.name}: {collaborators}")

            # Handle new additions
            additions = set(project.maintainers) - (collaborators | set(internal_team))
            for user in additions:
                logging.info("Adding user %s to %s", user, repo.name)
                repo.add_to_collaborators(user, permission="maintain")

            # Warn for removals of old maintainers
            removals = collaborators - (set(project.maintainers) | set(internal_team))
            for user in removals:
                logging.warning("Removing user %s from %s", user, repo.name)
                repo.remove_from_collaborators(user)

    def update_org(self, maintainers: set[str]) -> None:
        org_members = self.org.get_members()
        org_members_list = {member.login.lower() for member in org_members}
        logging.debug(f"Current organization members: {org_members_list}")

        # Handle new additions
        additions = maintainers - org_members_list

        for member in additions:
            user = self.github.get_user(member)
            if isinstance(user, AuthenticatedUser):
                continue
            logging.info("Adding %s to organization", member)
            self.org.invite_user(user, role="direct_member")


def parse_and_flatten(projects_yaml: str) -> Tuple[list[Project], list[str], set[str]]:
    with open(projects_yaml, "r") as f:
        data = yaml.safe_load(f)
        projects = []
        project_maintainers = []
        for _, project_meta in data["projects"].items():
            repos = []
            maintainers = []
            for repo in project_meta["repos"]:
                repos.append(repo)
            for maintainer in project_meta["maintainers"] or []:
                maintainers.append(maintainer.lower())
            project_maintainers.extend(maintainers)
            project = Project(repos=repos, maintainers=maintainers)
            projects.append(project)

        internal_team = []
        for _, users in data["internal_team"].items():
            for user in users:
                internal_team.append(user.lower())

        return projects, internal_team, set(project_maintainers)


def main():
    GITHUB_TOKEN = os.environ["X_GITHUB_TOKEN"]
    auth = Auth(GITHUB_TOKEN)

    projects, internal_team, maintainers = parse_and_flatten("projects.yaml")
    for project in projects:
        auth.update_project(project, internal_team)

    auth.update_org(maintainers)


if __name__ == "__main__":
    main()
