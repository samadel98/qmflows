"""Mock CP2K funcionality."""
import copy
from pathlib import Path
from typing import Callable

import numpy as np
import pytest
from assertionlib import assertion
from pytest_mock import MockFixture
from scm.plams import Cp2kResults, Molecule

from qmflows import cp2k, templates
from qmflows.packages import CP2K_Result
from qmflows.utils import InitRestart
from qmflows.warnings_qmflows import QMFlows_Warning
from qmflows.test_utils import (
    PATH,
    PATH_MOLECULES,
    fill_cp2k_defaults,
    requires_cp2k,
    stdout_to_logger,
    validate_status,
)


def mock_runner(mocker_instance, jobname: str) -> Callable[..., CP2K_Result]:
    """Create a Result instance using a mocked runner."""
    run_mocked = mocker_instance.patch("qmflows.run")
    run_mocked.return_value = CP2K_Result(
        templates.geometry,
        ETHYLENE,
        jobname,
        status="successful",
        dill_path=WORKDIR / jobname / f"{jobname}.dill",
        plams_dir=WORKDIR / jobname,
    )
    return run_mocked


# module constants
WORKDIR = PATH / "output_cp2k"
ETHYLENE = Molecule(PATH_MOLECULES / "ethylene.xyz")


def test_deepcopy(tmp_path: Path) -> None:
    """Test the copy of a result instance."""
    jobname = "cp2k_job"
    dill_path = WORKDIR / jobname / f"{jobname}.dill"
    plams_dir = WORKDIR / jobname
    result = CP2K_Result(templates.geometry, ETHYLENE, jobname,
                         dill_path=dill_path, plams_dir=plams_dir)

    copy_result = copy.deepcopy(result)

    with InitRestart(path=tmp_path, folder="test_deepcopy"):
        assertion.is_(copy_result.molecule, result.molecule)
        assertion.eq(copy_result.archive, result.archive)
        assertion.eq(copy_result.settings, result.settings)


@stdout_to_logger
def test_getattr_warning(tmp_path: Path) -> None:
    """Test that undefined properties warn, both before and after unpickling the results."""
    jobname = "cp2k_job"
    result = CP2K_Result(templates.geometry, ETHYLENE, jobname,
                         dill_path=WORKDIR / jobname / f"{jobname}.dill",
                         plams_dir=WORKDIR / jobname)

    # Need to fire up `plams.init` so the .dill file can be unpickled by `plams.load_job`
    with InitRestart(path=tmp_path, folder="test_getattr_warning"):
        for _ in range(2):
            with pytest.warns(QMFlows_Warning, match="Generic property 'bob' not defined") as rec:
                result.bob
            assertion.len_eq(rec.list, 1)
            assertion.eq(rec.list[0].filename, __file__)
        assertion.isinstance(result.results, Cp2kResults)


@stdout_to_logger
def test_unpickle_failure(tmp_path: Path) -> None:
    """Test that a .dill file which cannot be unpickled sets the results to ``None``."""
    dill_path = tmp_path / "broken.dill"
    dill_path.write_bytes(b"not a pickle")
    result = CP2K_Result(templates.geometry, ETHYLENE, "broken",
                         dill_path=dill_path, plams_dir=tmp_path)

    with InitRestart(path=tmp_path, folder="test_unpickle_failure"):
        with pytest.warns(QMFlows_Warning, match="Failed to unpickle"):
            assertion.is_(result.results, None)


@requires_cp2k
def test_cp2k_singlepoint_mock(mocker: MockFixture):
    """Mock a call to CP2K."""
    # single point calculation
    s = fill_cp2k_defaults(templates.singlepoint)

    # print orbitals
    s.specific.cp2k.force_eval.dft.print.mo.filename = (
        PATH / "orbitals.out").as_posix()
    s.specific.cp2k.force_eval.dft.print.mo.mo_index_range = "7 26"
    s.specific.cp2k.force_eval.dft.scf.added_mos = 20

    # Construct a result objects
    job = cp2k(s, ETHYLENE)
    jobname = "cp2k_job"
    run_mocked = mock_runner(mocker, jobname)
    rs = run_mocked(job)
    validate_status(rs)

    # electronic energy
    assertion.isfinite(rs.energy)

    # Molecular orbitals
    orbs = rs.orbitals
    assertion.assert_(np.isfinite, orbs.eigenvectors, post_process=np.all)  # eigenvalues
    assertion.shape_eq(orbs.eigenvectors, (46, 20))


def test_c2pk_opt_mock(mocker: MockFixture):
    """Mock a call to CP2K."""
    # geometry optimization input
    s = fill_cp2k_defaults(templates.geometry)

    jobname = "cp2k_opt"
    run_mocked = mock_runner(mocker, jobname)

    job = cp2k(s, ETHYLENE, job_name=jobname)
    rs = run_mocked(job)
    validate_status(rs)

    # check the optimized geometry
    mol = rs.geometry
    assertion.len_eq(mol, 6)
    atom = mol[1]
    assertion.len_eq(atom.coords, 3)
    assertion.eq(atom.symbol, 'C')


def test_c2pk_freq_mock(mocker: MockFixture):
    """Mock a call to CP2K."""
    # Frequency calculation
    s = fill_cp2k_defaults(templates.singlepoint)
    s.specific.cp2k.vibrational_analysis.thermochemistry = ".TRUE."
    s.specific.cp2k["global"]["run_type"] = "VIBRATIONAL_ANALYSIS"

    jobname = "cp2k_freq"
    run_mocked = mock_runner(mocker, jobname)
    job = cp2k(s, ETHYLENE, job_name=jobname)
    rs = run_mocked(job)
    validate_status(rs)

    # check properties
    assertion.isfinite(rs.enthalpy)
    assertion.isfinite(rs.free_energy)


def test_dir(mocker: MockFixture) -> None:
    s = fill_cp2k_defaults(templates.geometry)
    jobname = "cp2k_opt"
    run_mocked = mock_runner(mocker, jobname)

    job = cp2k(s, ETHYLENE, job_name=jobname)
    r = run_mocked(job)
    validate_status(r)

    assertion.issubset(CP2K_Result.prop_mapping.keys(), dir(r))
