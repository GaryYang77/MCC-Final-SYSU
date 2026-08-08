#include "cppdefs.h"
      MODULE mod_parallel
!
!svn $Id: mod_parallel.F 830 2017-01-24 21:21:11Z arango $
!================================================== Hernan G. Arango ===
!  Copyright (c) 2002-2017 The ROMS/TOMS Group                         !
!    Licensed under a MIT/X style license                              !
!    See License_ROMS.txt                                              !
!=======================================================================
!                                                                      !
!  This module contains all variables used for parallelization         !
!                                                                      !
!=======================================================================
!
      USE mod_param
!
      implicit none

#ifdef MPI
      include 'mpif.h'
#endif
!
!  Switch to identify master processor. In serial and shared-memory
!  applications it is always true.
!
      logical :: Master
!
!  Switch to identify which thread is processing input/output files.
!  In distributed-memory applications, this thread can be the master
!  thread or all threads in case of parallel output. In serial and
!  shared-memory applications it is always true.
!
      logical :: InpThread
      logical :: OutThread
!
!  Number of shared-memory parallel threads or distributed-memory
!  parallel nodes.
!
      integer :: numthreads
!
!  First and last tile to process in a tiled application.
!
      integer, allocatable :: first_tile(:)
      integer, allocatable :: last_tile(:)

!$OMP THREADPRIVATE (first_tile, last_tile)

#ifdef AIR_OCEAN
!
!  Parallel nodes assined to the atmosphere model.
!
      integer :: peATM_frst            ! first atmosphere parallel node
      integer :: peATM_last            ! last  atmosphere parallel node
#endif
#ifdef WAVES_OCEAN
!
!  Parallel nodes assined to the wave model.
!
      integer :: peWAV_frst            ! first atmosphere parallel node
      integer :: peWAV_last            ! last  atmosphere parallel node
#endif
!
!  Parallel nodes assined to the ocean model.
!
      integer :: peOCN_frst            ! first ocean parallel node
      integer :: peOCN_last            ! last  ocean parallel node
!
!  Parallel threads/nodes counters used in critical parallel regions.
!
      integer :: tile_count = 0
      integer :: block_count = 0
      integer :: thread_count = 0
!
!  Profiling variables as function of parallel thread:
!
!    proc          Parallel process ID.
!    Cstr          Starting wall time for program region.
!    Cend          Accumulated wall time for program region.
!    Csum          Wall time summed over parallel workers.
!    Cstr_cpu      Starting CPU time for program region.
!    Cend_cpu      Accumulated CPU time for program region.
!    Csum_cpu      CPU time summed over parallel workers.
!    Ccalls        Completed calls to a program region.
!    Csum_calls    Calls summed over parallel workers.
!
      integer, allocatable :: proc(:,:,:)

      real(r8), allocatable :: Cstr(:,:,:)
      real(r8), allocatable :: Cend(:,:,:)
      real(r8), allocatable :: Csum(:,:,:)
      real(r8), allocatable :: Cstr_cpu(:,:,:)
      real(r8), allocatable :: Cend_cpu(:,:,:)
      real(r8), allocatable :: Csum_cpu(:,:,:)
      real(r8), allocatable :: Ccalls(:,:,:)
      real(r8), allocatable :: Csum_calls(:,:,:)

#if defined PROFILE_DIAGNOSTIC && defined DISTRIBUTE
!
!  Profiler-v2 diagnostic state.  These arrays exist only in a dedicated
!  diagnostic binary; the score PROFILE binary has no calls or storage.
!
      integer, parameter :: MaxProfileSites = 200
      integer, parameter :: MaxProfileTraceEvents = 200000

      logical :: ProfileDiagnostic = .FALSE.
      logical :: ProfileTrace = .FALSE.
      logical :: ProfileTraceRank = .FALSE.
      logical :: ProfileInitialized = .FALSE.

      integer :: ProfileTraceCount = 0
      integer :: ProfileTraceDropped = 0
      integer :: ProfileTraceLimit = 100000
      integer :: ProfileLocalRank = 0

      character (len=16) :: ProfileMode = 'score'
      character (len=64) :: ProfileNode = 'unknown'
      character (len=512) :: ProfileDiagDir = '.'

      real(r8) :: ProfileClockStartLocal = 0.0_r8
      real(r8) :: ProfileClockStartOffset = 0.0_r8
      real(r8) :: ProfileClockStartRtt = 0.0_r8
      real(r8) :: ProfileClockEndLocal = 0.0_r8
      real(r8) :: ProfileClockEndOffset = 0.0_r8
      real(r8) :: ProfileClockEndRtt = 0.0_r8

      real(r8), allocatable :: PsiteStart(:,:,:)
      real(r8), allocatable :: PsiteWall(:,:,:)
      real(r8), allocatable :: PsiteCalls(:,:,:)
      real(r8), allocatable :: PsiteBytesSent(:,:,:)
      real(r8), allocatable :: PsiteBytesRecv(:,:,:)
      integer, allocatable :: PsitePeersMax(:,:,:)

      integer, allocatable :: PtraceGrid(:)
      integer, allocatable :: PtraceModel(:)
      integer, allocatable :: PtraceSite(:)
      integer, allocatable :: PtracePeers(:)
      real(r8), allocatable :: PtraceStart(:)
      real(r8), allocatable :: PtraceEnd(:)
      real(r8), allocatable :: PtraceBytesSent(:)
      real(r8), allocatable :: PtraceBytesRecv(:)
#endif

!$OMP THREADPRIVATE (proc)
!$OMP THREADPRIVATE (Cstr, Cend, Cstr_cpu, Cend_cpu, Ccalls)

#if defined DISTRIBUTE && defined PROFILE
!
!  Switch manage time clock in "mp_bcasts". During initialization is
!  set to .FALSE. because the profiling variables cannot be allocated
!  and initialized before the "Ngrids" parameter is known.
!
      logical :: Lwclock = .FALSE.
#endif
!
!  Distributed-memory master process.
!
      integer, parameter :: MyMaster = 0
!
!  Rank of the parallel local process.
!
      integer :: MyRank = 0
      integer :: MyThread = 0

!$OMP THREADPRIVATE (MyThread)

#ifdef DISTRIBUTE
# ifdef MPI
!
!  Ocean model MPI group communicator handle.
!
      integer :: OCN_COMM_WORLD
!
!  Set mpi_info opaque object handle.
!
      integer :: MP_INFO = MPI_INFO_NULL
# endif
!
!  Type of message-passage floating point bindings.
!
# ifdef DOUBLE_PRECISION
#  ifdef MPI
      integer, parameter :: MP_FLOAT = MPI_DOUBLE_PRECISION
!!    integer, parameter :: MP_FLOAT = MPI_REAL8
#  endif
# else
#  ifdef MPI
      integer, parameter :: MP_FLOAT = MPI_REAL
!!    integer, parameter :: MP_FLOAT = MPI_REAL4
#  endif
# endif
#endif
!
      CONTAINS
!
      SUBROUTINE allocate_parallel
!
!=======================================================================
!                                                                      !
!  This routine allocates several variables in the module that depend  !
!  on the number of nested grids.                                      !
!                                                                      !
!=======================================================================
!
      USE mod_strings, ONLY: Nregion
!
!-----------------------------------------------------------------------
!  Allocate and initialize module variables.
!-----------------------------------------------------------------------
!
!$OMP PARALLEL
!  First and last tile to process in a tiled application.
!
      allocate ( first_tile(Ngrids) )
      allocate ( last_tile (Ngrids) )
!
!  Time profiling variables.
!
      allocate ( proc(0:1,4,Ngrids) )
      proc(0:1,1:4,1:Ngrids)=0

      allocate ( Cstr(0:Nregion,4,Ngrids) )
      Cstr(0:Nregion,1:4,1:Ngrids)=0.0_r8

      allocate ( Cend(0:Nregion,4,Ngrids) )
      Cend(0:Nregion,1:4,1:Ngrids)=0.0_r8

      allocate ( Cstr_cpu(0:Nregion,4,Ngrids) )
      Cstr_cpu(0:Nregion,1:4,1:Ngrids)=0.0_r8

      allocate ( Cend_cpu(0:Nregion,4,Ngrids) )
      Cend_cpu(0:Nregion,1:4,1:Ngrids)=0.0_r8

      allocate ( Ccalls(0:Nregion,4,Ngrids) )
      Ccalls(0:Nregion,1:4,1:Ngrids)=0.0_r8
!$OMP END PARALLEL
      allocate ( Csum(0:Nregion,4,Ngrids) )
      Csum(0:Nregion,1:4,1:Ngrids)=0.0_r8

      allocate ( Csum_cpu(0:Nregion,4,Ngrids) )
      Csum_cpu(0:Nregion,1:4,1:Ngrids)=0.0_r8

      allocate ( Csum_calls(0:Nregion,4,Ngrids) )
      Csum_calls(0:Nregion,1:4,1:Ngrids)=0.0_r8

#if defined PROFILE_DIAGNOSTIC && defined DISTRIBUTE
      allocate (PsiteStart(MaxProfileSites,4,Ngrids))
      allocate (PsiteWall(MaxProfileSites,4,Ngrids))
      allocate (PsiteCalls(MaxProfileSites,4,Ngrids))
      allocate (PsiteBytesSent(MaxProfileSites,4,Ngrids))
      allocate (PsiteBytesRecv(MaxProfileSites,4,Ngrids))
      allocate (PsitePeersMax(MaxProfileSites,4,Ngrids))
      PsiteStart=0.0_r8
      PsiteWall=0.0_r8
      PsiteCalls=0.0_r8
      PsiteBytesSent=0.0_r8
      PsiteBytesRecv=0.0_r8
      PsitePeersMax=0

      allocate (PtraceGrid(MaxProfileTraceEvents))
      allocate (PtraceModel(MaxProfileTraceEvents))
      allocate (PtraceSite(MaxProfileTraceEvents))
      allocate (PtracePeers(MaxProfileTraceEvents))
      allocate (PtraceStart(MaxProfileTraceEvents))
      allocate (PtraceEnd(MaxProfileTraceEvents))
      allocate (PtraceBytesSent(MaxProfileTraceEvents))
      allocate (PtraceBytesRecv(MaxProfileTraceEvents))
      PtraceGrid=0
      PtraceModel=0
      PtraceSite=0
      PtracePeers=0
      PtraceStart=0.0_r8
      PtraceEnd=0.0_r8
      PtraceBytesSent=0.0_r8
      PtraceBytesRecv=0.0_r8
#endif

#if defined DISTRIBUTE && defined PROFILE
!
! Activate wall clock switch used only in "mp_bcasts". This switch
! is set to .FALSE. during initialization before calling "inp_par.F"
! because the above profiling variables are allocated and initialized
! after the value of "Ngrids" is known.
!
      Lwclock=.TRUE.
#endif

      RETURN
      END SUBROUTINE allocate_parallel

      SUBROUTINE initialize_parallel
!
!=======================================================================
!                                                                      !
!  This routine initializes and spawn distribute-memory nodes.         !
!                                                                      !
!=======================================================================
!
      USE mod_iounits
      USE mod_scalars
!
!  Local variable declarations.
!
      integer :: i
#ifdef DISTRIBUTE
      integer :: MyError
#else
      integer :: my_numthreads
#endif
!
!-----------------------------------------------------------------------
!  Initialize shared-memory (OpenMP) or serial configuration.
!-----------------------------------------------------------------------

#ifdef _OPENMP
!
!  Disable dynamic adjustment, by the run-time environment, of the
!  number of threads available to execute parallel regions.
!
      CALL omp_set_dynamic (.FALSE.)
#endif
#ifndef DISTRIBUTE
!
!  Inquire number of threads in parallel region.
!
      numthreads=my_numthreads()
      Master=.TRUE.
      InpThread=.TRUE.
      OutThread=.TRUE.
#endif
#ifdef DISTRIBUTE
# ifdef MPI
!
!-----------------------------------------------------------------------
!  Initialize distributed-memory (MPI) configuration.
!-----------------------------------------------------------------------
!
!  Get the number of processes in the group associated with the world
!  communicator.
!
      CALL mpi_comm_size (OCN_COMM_WORLD, numthreads, MyError)
      IF (MyError.ne.0) THEN
        WRITE (stdout,10)
  10    FORMAT (/,' ROMS/TOMS - Unable to inquire number of',           &
     &            ' processors in the group.')
        exit_flag=6
        RETURN
      END IF
!
!  Identify master, input and output threads.
!
#  ifdef PARALLEL_IO
      Master=.FALSE.
      InpThread=.TRUE.
      OutThread=.TRUE.
      IF (MyRank.eq.MyMaster) THEN
        Master=.TRUE.
      END IF
#  else
      Master=.FALSE.
      InpThread=.FALSE.
      OutThread=.FALSE.
      IF (MyRank.eq.MyMaster) THEN
        Master=.TRUE.
        InpThread=.TRUE.
        OutThread=.TRUE.
      END IF
#  endif
# endif
#endif

      RETURN
      END SUBROUTINE initialize_parallel

      END MODULE mod_parallel
