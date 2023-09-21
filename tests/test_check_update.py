import shutil
from pathlib import Path

import pytest
from plumbum import local
from plumbum.cmd import git

import copier
from copier.errors import DirtyLocalWarning, SubprojectOutdatedError, UserMessageError

from .helpers import build_file_tree


@pytest.fixture
def setup_git_tracked_template(tmp_path_factory: pytest.TempPathFactory):
    src, dst = map(tmp_path_factory.mktemp, ("src", "dst"))

    build_file_tree(
        {
            (src / ".copier-answers.yml.jinja"): (
                """\
                # Changes here will be overwritten by Copier
                {{ _copier_answers|to_nice_yaml }}
                """
            ),
            (src / "copier.yml"): (
                """\
                _envops:
                    "keep_trailing_newline": True
                """
            ),
            (src / "aaaa.txt"): (
                """
                Lorem ipsum
                """
            ),
            (src / "to_delete.txt"): (
                """
                delete me.
                """
            ),
        }
    )

    with local.cwd(src):
        git("init")
        git("add", "-A")
        git("commit", "-m", "first commit on src")

    copier.run_copy(str(src), dst, defaults=True, overwrite=True)
    yield src, dst
    shutil.rmtree(src)
    shutil.rmtree(dst)


def test_fails_when_no_template_ref(tmp_path_factory: pytest.TempPathFactory) -> None:
    src, dst = map(tmp_path_factory.mktemp, ("src", "dst"))

    build_file_tree(
        {
            (src / "aaaa.txt"): (
                """
                Lorem ipsum
                """
            )
        }
    )
    with pytest.raises(UserMessageError) as excinfo:
        copier.run_check_update(dst, None, defaults=True, overwrite=True)

    assert "Cannot check because cannot obtain old template references" in str(
        excinfo.value
    )


def test_check_update_when_updates_needed(
    setup_git_tracked_template: tuple[Path, Path],
) -> None:
    src, dst = setup_git_tracked_template

    with local.cwd(src):
        # test adding a file
        Path("test_file.txt").write_text("Test content")

        # test updating a file
        with open("aaaa.txt", "a") as f:
            f.write("dolor sit amet")

    # dst must be vcs-tracked to use check_update
    with local.cwd(dst):
        git("init")
        git("add", "-A")
        git("commit", "-m", "first commit on dst")

    with pytest.warns(DirtyLocalWarning):
        with pytest.raises(SubprojectOutdatedError):
            copier.run_check_update(dst, None, defaults=True, overwrite=True)
