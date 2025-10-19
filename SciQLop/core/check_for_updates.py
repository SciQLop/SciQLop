# Description: Check for updates on the SciQLop repository
from typing import List
from speasy.core.cache import CacheCall


class ReleaseAsset:
    def __init__(self, name: str, url: str, content_type: str, size: int):
        self._name = name
        self._url = url
        self._content_type = content_type
        self._size = size

    @property
    def name(self):
        return self._name

    @property
    def url(self):
        return self._url

    @property
    def content_type(self):
        return self._content_type

    @property
    def size(self):
        return self._size

    def __repr__(self):
        return f"""{self.name} {self.content_type} {self.size}
{self.url}"""


class SciQLopRelease:
    def __init__(self, title: str, tag_name: str, url: str, body: str, assets: List[ReleaseAsset]):
        self._title = title
        self._tag_name = tag_name
        self._url = url
        self._body = body
        self._assets = assets

    @property
    def title(self):
        return self._title

    @property
    def tag_name(self):
        return self._tag_name

    @property
    def version(self):
        return self._tag_name.replace("v", "")

    @property
    def url(self):
        return self._url

    @property
    def body(self):
        return self._body

    @property
    def assets(self):
        return self._assets

    def __repr__(self):
        return f"""{self.title}
{self.tag_name}
{self.url}
{self.body}""" + "\n".join([f"\n{a}" for a in self.assets])


@CacheCall(3600)
def get_latest_release() -> SciQLopRelease or None:
    try:
        from github import Github
        gh = Github()
        repo = gh.get_repo("SciQLop/SciQLop")
        r = repo.get_latest_release()
        return SciQLopRelease(r.title, r.tag_name, r.html_url, r.body,
                              [ReleaseAsset(a.name, a.url, a.content_type, a.size) for a in r.get_assets()])
    except ImportError:
        return None


def current_version() -> str:
    from SciQLop import __version__
    return __version__
