from __future__ import annotations


class PanagerError(Exception):
    """패니저 애플리케이션의 기본 예외 클래스."""


class GoogleAuthRequired(PanagerError):
    """Google 계정 미연동 또는 권한 부족 시 발생하는 예외."""


class GithubAuthRequired(PanagerError):
    """GitHub 계정 미연동 시 발생하는 예외."""


class NotionAuthRequired(PanagerError):
    """Notion 계정 미연동 시 발생하는 예외."""
