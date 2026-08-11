from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MP_ROUTINES = ROOT / "ROMS_CoSiNE15" / "ROMS" / "Utility" / "mp_routines.F"
MOD_PARALLEL = ROOT / "ROMS_CoSiNE15" / "ROMS" / "Modules" / "mod_parallel.F"
MOD_STRINGS = ROOT / "ROMS_CoSiNE15" / "ROMS" / "Modules" / "mod_strings.F"
TIMERS = ROOT / "ROMS_CoSiNE15" / "ROMS" / "Utility" / "timers.F"
SYNC_TO_CLUSTER = ROOT / "Local_Lab" / "sync_to_cluster.sh"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_wall_clock_uses_elapsed_time_sources_not_cpu_time() -> None:
    source = _source(MP_ROUTINES)
    wall_clock = source.split("FUNCTION my_wtime", 1)[1].split(
        "END FUNCTION my_wtime", 1
    )[0]

    assert "MPI_WTIME()" in wall_clock
    assert "omp_get_wtime()" in wall_clock
    assert "CALL system_clock" in wall_clock
    assert "CALL cpu_time" not in wall_clock


def test_cpu_clock_remains_available_as_an_independent_measurement() -> None:
    source = _source(MP_ROUTINES)
    cpu_clock = source.split("FUNCTION my_ctime", 1)[1].split(
        "END FUNCTION my_ctime", 1
    )[0]

    assert "CALL cpu_time" in cpu_clock


def test_profiling_allocates_separate_wall_and_cpu_accumulators() -> None:
    source = _source(MOD_PARALLEL)

    for name in ("Cstr_cpu", "Cend_cpu", "Csum_cpu"):
        assert f"real(r8), allocatable :: {name}" in source
        assert f"allocate ( {name}(0:Nregion,4,Ngrids) )" in source


def test_timers_default_to_wall_clock_with_optional_cpu_measurements() -> None:
    source = _source(TIMERS)

    assert "my_ctime" in source
    assert "Csum_cpu" in source
    assert "Wall:" in source
    assert "CPU:" in source
    assert "total wall time" in source.lower()
    assert source.count("#ifdef PROFILE_CPU") >= 2


def test_profiling_counts_completed_region_calls_locally() -> None:
    parallel_source = _source(MOD_PARALLEL)
    timer_source = _source(TIMERS)

    assert "real(r8), allocatable :: Ccalls" in parallel_source
    assert "allocate ( Ccalls(0:Nregion,4,Ngrids) )" in parallel_source
    assert "Ccalls(region,MyModel,ng)=Ccalls(region,MyModel,ng)+1.0_r8" in (
        timer_source.replace(" ", "")
    )


def test_rank_statistics_are_reduced_only_during_finalization() -> None:
    source = _source(TIMERS)
    hot_path, finalization = source.split("IF ((region.eq.0)", 1)

    assert "CALL mp_reduce" not in hot_path
    for operation in ("'MIN'", "'SUM'", "'MAX'"):
        assert operation in finalization
    assert "wall_max_rank" in finalization
    assert "PROFILE_RANK" in finalization


def test_machine_readable_profile_classifies_io_and_mpi_regions() -> None:
    source = _source(TIMERS)

    assert "region_kind='io_read'" in source
    assert "region_kind='io_write'" in source
    assert "region_kind='mpi'" in source
    assert "' kind=',a" in source


def test_nesting_region_39_wraps_all_exit_paths() -> None:
    source = _source(
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear" / "nesting.F"
    )
    main_routine = source.split("END SUBROUTINE nesting", 1)[0]

    assert "CALL wclock_on (ng, model, 39)" in main_routine
    assert "CALL wclock_off (ng, model, 39)" in main_routine
    assert "CALL wclock_on (ng, model, nest_region)" in main_routine
    assert "CALL wclock_off (ng, model, nest_region)" in main_routine
    for region in range(51, 57):
        assert f"nest_region={region}" in main_routine
    assert main_routine.count("GO TO 10") == 4


def test_nesting_detail_regions_do_not_expand_the_mpi_region_range() -> None:
    strings = _source(MOD_STRINGS)
    timers = _source(TIMERS)

    assert "integer, parameter :: NregionMPI = 50" in strings
    assert "integer, parameter :: MregionNesting = 51" in strings
    assert "integer, parameter :: Nregion = 56" in strings
    assert "iregion.le.NregionMPI" in timers
    assert "DO iregion=Mregion,NregionMPI" in timers
    assert "DO iregion=MregionNesting,Nregion" in timers
    assert "model nesting section profile" in timers


def test_cluster_sync_preserves_official_launch_results() -> None:
    source = _source(SYNC_TO_CLUSTER)

    assert "--delete" in source
    assert "--exclude '/sysu_official_launch/run_*/'" in source
    assert "--exclude '/sysu_official_launch/slurm_*.out'" in source
    assert "--exclude '/sysu_official_launch/slurm_*.err'" in source
