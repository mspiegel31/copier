from pathlib import Path

import pytest
from plumbum import local
from plumbum.cmd import git

import copier
from copier.errors import DirtyLocalWarning, SubprojectOutdatedError

from .helpers import build_file_tree


def test_check_update_when_updates_needed(
    tmp_path_factory: pytest.TempPathFactory,
    capsys: pytest.CaptureFixture[str],
) -> None:
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
            (src / "symlink.txt"): Path("./to_delete.txt"),
        }
    )

    with local.cwd(src):
        git("init")
        git("add", "-A")
        git("commit", "-m", "first commit on src")

    copier.run_copy(str(src), dst, defaults=True, overwrite=True)

    with local.cwd(src):
        # test adding a file
        Path("test_file.txt").write_text("Test content")

        # test updating a file
        with open("aaaa.txt", "a") as f:
            f.write("dolor sit amet")

        # test updating a symlink
        Path("symlink.txt").unlink()
        Path("symlink.txt").symlink_to("test_file.txt")

        # test removing a file
        Path("to_delete.txt").unlink()

    # dst must be vcs-tracked to use run_update
    with local.cwd(dst):
        git("init")
        git("add", "-A")
        git("commit", "-m", "first commit on dst")

    # make sure changes have not yet propagated
    assert not (dst / "test_file.txt").exists()

    assert (src / "aaaa.txt").read_text() != (dst / "aaaa.txt").read_text()

    p1 = src / "symlink.txt"
    p2 = dst / "symlink.txt"
    assert p1.read_text() != p2.read_text()

    assert (dst / "to_delete.txt").exists()

    with pytest.warns(DirtyLocalWarning):
        with pytest.raises(SubprojectOutdatedError):
            copier.run_check_update(dst, None, defaults=True, overwrite=True)
