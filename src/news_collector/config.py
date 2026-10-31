import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    pass


# type ごとに、取得対象を指定するキー
_TARGET_KEY = {
    "zenn": "tag",
    "qiita": "tag",
    "github_releases": "repo",
}


_LABEL_PREFIX = {
    "zenn": "zenn",
    "qiita": "qiita",
    "github_releases": "github",
}


@dataclass(frozen=True)
class SourceConfig:
    type: str
    target: str  # zenn / qiita ならタグ名、github_releases なら "owner/repo"

    @property
    def label(self) -> str:
        """DB の source 列やログに使う名前。例: "zenn:claudecode"。"""
        return f"{_LABEL_PREFIX[self.type]}:{self.target}"


@dataclass(frozen=True)
class Config:
    db_path: Path
    sources: list[SourceConfig]


def load_config(path) -> Config:
    path = Path(path)
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"設定ファイルが見つかりません: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"設定ファイルを読めません ({path}): {e}") from None

    try:
        db_path = path.parent / data["database"]["path"]
    except KeyError:
        raise ConfigError("[database] の path が必要です") from None

    sources = [_parse_source(raw) for raw in data.get("sources", [])]
    if not sources:
        raise ConfigError("[[sources]] が 1 つも設定されていません")

    return Config(db_path=db_path, sources=sources)


def _parse_source(raw: dict) -> SourceConfig:
    source_type = raw.get("type")
    key = _TARGET_KEY.get(source_type)
    if key is None:
        raise ConfigError(f"未知の type です: {source_type!r}")
    if key not in raw:
        raise ConfigError(f"type = {source_type!r} には {key} が必要です")
    return SourceConfig(type=source_type, target=raw[key])
