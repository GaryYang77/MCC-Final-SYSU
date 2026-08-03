#include "cppdefs.h"
      SUBROUTINE wclock_on (ng, model, region)
!
!svn $Id: timers.F 830 2017-01-24 21:21:11Z arango $
!=======================================================================
!  Copyright (c) 2002-2017 The ROMS/TOMS Group                         !
!    Licensed under a MIT/X style license                              !
!    See License_ROMS.txt                           Hernan G. Arango   !
!========================================== Alexander F. Shchepetkin ===
!                                                                      !
!  This routine turns on wall clock to meassure the elapsed time in    !
!  seconds spend by each parallel thread in requested model region.    !
!                                                                      !
!=======================================================================
!
      USE mod_param
      USE mod_parallel
      USE mod_iounits
      USE mod_strings
#ifdef DISTRIBUTE
!
      USE distribute_mod, ONLY : mp_barrier
#endif
!
      implicit none
!
!  Imported variable declarations.
!
      integer, intent(in) ::  ng, model, region
!
!  Local variable declarations.
!
      integer :: iregion, MyModel, NSUB

      integer :: my_getpid
#ifndef DISTRIBUTE
      integer :: my_threadnum
#endif

      real(r8), dimension(2) :: wtime

      real(r8) :: my_ctime, my_wtime
!
!-----------------------------------------------------------------------
! Initialize timing for all threads.
!-----------------------------------------------------------------------
!
!  Set number of subdivisions, same as for global reductions.
!
#ifdef MPI
      NSUB=1
#else
      NSUB=numthreads
#endif
!
!  Insure that MyModel is not zero.  Notice that zero value is used to
!  indicate restart of the nonlinear model.
!
      MyModel=MAX(1,model)
      Cstr(region,MyModel,ng)=my_wtime(wtime)
#ifdef PROFILE_CPU
      Cstr_cpu(region,MyModel,ng)=my_ctime()
#else
      Cstr_cpu(region,MyModel,ng)=0.0_r8
#endif
      IF ((region.eq.0).and.(proc(1,MyModel,ng).eq.0)) THEN
        DO iregion=1,Nregion
          Cend(iregion,MyModel,ng)=0.0_r8
          Csum(iregion,MyModel,ng)=0.0_r8
          Cend_cpu(iregion,MyModel,ng)=0.0_r8
          Csum_cpu(iregion,MyModel,ng)=0.0_r8
          Ccalls(iregion,MyModel,ng)=0.0_r8
          Csum_calls(iregion,MyModel,ng)=0.0_r8
        END DO
        proc(1,MyModel,ng)=1
        proc(0,MyModel,ng)=my_getpid()

!$OMP CRITICAL (START_WCLOCK)
#ifdef DISTRIBUTE
        CALL mp_barrier (ng)
        WRITE (stdout,10) ' Node #', MyRank,                            &
     &                    ' (pid=',proc(0,MyModel,ng),') is active.'
        CALL my_flush (stdout)
#else
        WRITE (stdout,10) ' Thread #', MyThread,                        &
     &                    ' (pid=',proc(0,MyModel,ng),') is active.'
#endif
 10     FORMAT (a,i3,a,i8,a)
        thread_count=thread_count+1
        IF (thread_count.eq.NSUB) thread_count=0
!$OMP END CRITICAL (START_WCLOCK)
      END IF
      RETURN
      END SUBROUTINE wclock_on
      SUBROUTINE wclock_off (ng, model, region)
!
!=======================================================================
!                                                                      !
!  This routine turns off wall clock to meassure the elapsed time in   !
!  seconds spend by each parallel thread in requested model region.    !
!                                                                      !
!=======================================================================
!
      USE mod_param
      USE mod_parallel
      USE mod_iounits
      USE mod_strings
#ifdef DISTRIBUTE
!
      USE distribute_mod, ONLY : mp_barrier, mp_reduce
#endif
!
      implicit none
!
!  Imported variable declarations.
!
      integer, intent(in) ::  ng, model, region
!
!  Local variable declarations.
!
      integer :: imodel, iregion, MyModel, NSUB

      integer :: my_threadnum

      real(r8) :: cpu_now, imbalance, percent, sumcpu, sumper
      real(r8) :: sumwall, total, totalcpu, wall_now, workers

      real(r8), dimension(0:Nregion,4) :: calls_sum
      real(r8), dimension(0:Nregion,4) :: cpu_max, cpu_mean
      real(r8), dimension(0:Nregion,4) :: cpu_min
      real(r8), dimension(0:Nregion,4) :: wall_max, wall_mean
      real(r8), dimension(0:Nregion,4) :: wall_min
      real(r8), dimension(0:Nregion,4) :: wall_max_rank

      real(r8), dimension(2) :: wtime

      real(r8) :: my_ctime, my_wtime

#ifdef DISTRIBUTE
      real(r8), dimension(0:Nregion) :: buffer
      real(r8), dimension(0:Nregion) :: cpu_buffer
      real(r8), dimension(0:Nregion) :: rank_buffer

      character (len= 3), dimension(0:Nregion) :: op_handle
#endif
      character (len=14), dimension(4) :: label
      character (len= 8) :: region_kind
!
!-----------------------------------------------------------------------
!  Compute elapsed wall time for all threads.
!-----------------------------------------------------------------------
!
!  Set number of subdivisions, same as for global reductions.
!
#ifdef MPI
      NSUB=1
#else
      NSUB=numthreads
#endif
!
!  Insure that MyModel is not zero.  Notice that zero value is used to
!  indicate restart of the nonlinear model.
!
      MyModel=MAX(1,model)
      wall_now=my_wtime(wtime)
#ifdef PROFILE_CPU
      cpu_now=my_ctime()
#else
      cpu_now=0.0_r8
#endif
      IF (region.ne.0) THEN
        Cend(region,MyModel,ng)=Cend(region,MyModel,ng)+                &
     &                          (wall_now-                             &
     &                           Cstr(region,MyModel,ng))
        Cend_cpu(region,MyModel,ng)=Cend_cpu(region,MyModel,ng)+        &
     &                              (cpu_now-                          &
     &                               Cstr_cpu(region,MyModel,ng))
        Ccalls(region,MyModel,ng)=Ccalls(region,MyModel,ng)+1.0_r8
      END IF
!
!  Report elapsed wall time.
!
      IF ((region.eq.0).and.(proc(1,MyModel,ng).eq.1)) THEN
        Cend(region,MyModel,ng)=Cend(region,MyModel,ng)+                &
     &                          (wall_now-                             &
     &                           Cstr(region,MyModel,ng))
        Cend_cpu(region,MyModel,ng)=Cend_cpu(region,MyModel,ng)+        &
     &                              (cpu_now-                          &
     &                               Cstr_cpu(region,MyModel,ng))
        Ccalls(region,MyModel,ng)=Ccalls(region,MyModel,ng)+1.0_r8
        DO imodel=1,4
          proc(1,imodel,ng)=0
        END DO

!$OMP CRITICAL (FINALIZE_WCLOCK)
!
!  Report total elapsed time (seconds) for each CPU.  We get the same
!  time for all nested grids.
!
        IF (ng.eq.1) THEN
#ifdef DISTRIBUTE
          CALL mp_barrier (ng)
          WRITE (stdout,10) ' Node   #', MyRank, ' Wall:',              &
     &                      Cend(region,MyModel,ng), ' CPU:',           &
     &                      Cend_cpu(region,MyModel,ng)
         CALL my_flush (stdout)
#else
         WRITE (stdout,10) ' Thread #', MyThread, ' Wall:',             &
     &                     Cend(region,MyModel,ng), ' CPU:',            &
     &                     Cend_cpu(region,MyModel,ng)
#endif
 10      FORMAT (a,i3,a,f12.3,a,f12.3)
       END IF
!
! Report elapsed time profile for each region of the code.
!
        thread_count=thread_count+1
        DO imodel=1,4
          Csum(region,imodel,ng)=Csum(region,imodel,ng)+                &
     &                           Cend(region,imodel,ng)
          Csum_cpu(region,imodel,ng)=Csum_cpu(region,imodel,ng)+        &
     &                               Cend_cpu(region,imodel,ng)
          Csum_calls(region,imodel,ng)=                               &
     &      Csum_calls(region,imodel,ng)+Ccalls(region,imodel,ng)
          DO iregion=1,Nregion
            Csum(iregion,imodel,ng)=Csum(iregion,imodel,ng)+            &
     &                              Cend(iregion,imodel,ng)
            Csum_cpu(iregion,imodel,ng)=                               &
     &        Csum_cpu(iregion,imodel,ng)+Cend_cpu(iregion,imodel,ng)
            Csum_calls(iregion,imodel,ng)=                            &
     &        Csum_calls(iregion,imodel,ng)+Ccalls(iregion,imodel,ng)
          END DO
        END DO
        DO imodel=1,4
          IF (imodel.ne.MyModel) THEN
            DO iregion=1,Nregion
              Csum(region,imodel,ng)=Csum( region,imodel,ng)+           &
     &                               Csum(iregion,imodel,ng)
              Csum_cpu(region,imodel,ng)=                              &
     &          Csum_cpu(region,imodel,ng)+Csum_cpu(iregion,imodel,ng)
              Csum_calls(region,imodel,ng)=                           &
     &          Csum_calls(region,imodel,ng)+                         &
     &          Csum_calls(iregion,imodel,ng)
            END DO
          END IF
        END DO
        IF (thread_count.eq.NSUB) THEN
          thread_count=0
          workers=REAL(numthreads,r8)
          DO imodel=1,4
            DO iregion=0,Nregion
              wall_min(iregion,imodel)=Csum(iregion,imodel,ng)
              wall_mean(iregion,imodel)=Csum(iregion,imodel,ng)
              wall_max(iregion,imodel)=Csum(iregion,imodel,ng)
              cpu_min(iregion,imodel)=Csum_cpu(iregion,imodel,ng)
              cpu_mean(iregion,imodel)=Csum_cpu(iregion,imodel,ng)
              cpu_max(iregion,imodel)=Csum_cpu(iregion,imodel,ng)
              calls_sum(iregion,imodel)=                             &
     &          Csum_calls(iregion,imodel,ng)
              wall_max_rank(iregion,imodel)=REAL(MyRank,r8)
            END DO
          END DO
#ifdef DISTRIBUTE
          DO imodel=1,4
            op_handle(0:Nregion)='MIN'
            buffer(0:Nregion)=wall_min(0:Nregion,imodel)
            CALL mp_reduce (ng, MyModel, Nregion+1, buffer(0:),         &
     &                      op_handle(0:))
            wall_min(0:Nregion,imodel)=buffer(0:Nregion)
            cpu_buffer(0:Nregion)=cpu_min(0:Nregion,imodel)
            CALL mp_reduce (ng, MyModel, Nregion+1, cpu_buffer(0:),     &
     &                      op_handle(0:))
            cpu_min(0:Nregion,imodel)=cpu_buffer(0:Nregion)

            op_handle(0:Nregion)='MAX'
            buffer(0:Nregion)=wall_max(0:Nregion,imodel)
            CALL mp_reduce (ng, MyModel, Nregion+1, buffer(0:),         &
     &                      op_handle(0:))
            wall_max(0:Nregion,imodel)=buffer(0:Nregion)
            cpu_buffer(0:Nregion)=cpu_max(0:Nregion,imodel)
            CALL mp_reduce (ng, MyModel, Nregion+1, cpu_buffer(0:),     &
     &                      op_handle(0:))
            cpu_max(0:Nregion,imodel)=cpu_buffer(0:Nregion)

            DO iregion=0,Nregion
              IF (wall_mean(iregion,imodel).eq.                       &
     &            wall_max(iregion,imodel)) THEN
                rank_buffer(iregion)=REAL(MyRank,r8)
              ELSE
                rank_buffer(iregion)=REAL(numthreads,r8)
              END IF
            END DO
            op_handle(0:Nregion)='MIN'
            CALL mp_reduce (ng, MyModel, Nregion+1, rank_buffer(0:),    &
     &                      op_handle(0:))
            wall_max_rank(0:Nregion,imodel)=rank_buffer(0:Nregion)

            op_handle(0:Nregion)='SUM'
            buffer(0:Nregion)=wall_mean(0:Nregion,imodel)
            cpu_buffer(0:Nregion)=cpu_mean(0:Nregion,imodel)
            rank_buffer(0:Nregion)=calls_sum(0:Nregion,imodel)
            CALL mp_reduce (ng, MyModel, Nregion+1, buffer(0:),         &
     &                      op_handle(0:))
            CALL mp_reduce (ng, MyModel, Nregion+1, cpu_buffer(0:),     &
     &                      op_handle(0:))
            CALL mp_reduce (ng, MyModel, Nregion+1, rank_buffer(0:),    &
     &                      op_handle(0:))
            DO iregion=0,Nregion
              Csum(iregion,imodel,ng)=buffer(iregion)
              Csum_cpu(iregion,imodel,ng)=cpu_buffer(iregion)
              wall_mean(iregion,imodel)=buffer(iregion)/workers
              cpu_mean(iregion,imodel)=cpu_buffer(iregion)/workers
              calls_sum(iregion,imodel)=rank_buffer(iregion)
            END DO
          END DO
#endif
#ifndef DISTRIBUTE
          wall_mean(0:Nregion,1:4)=wall_mean(0:Nregion,1:4)/workers
          cpu_mean(0:Nregion,1:4)=cpu_mean(0:Nregion,1:4)/workers
#endif
          IF (Master.and.(ng.eq.1)) THEN
            total=0.0_r8
            totalcpu=0.0_r8
            DO imodel=1,4
              total=total+Csum(region,imodel,ng)
              totalcpu=totalcpu+Csum_cpu(region,imodel,ng)
            END DO
            WRITE (stdout,20) ' Total rank wall seconds:', total
            WRITE (stdout,20) ' Total rank CPU  seconds:', totalcpu
 20         FORMAT (a,1x,f14.3)
          END IF
#ifdef PROFILE
!
!  Report profiling times.
!
          label(iNLM)='Nonlinear     '
          label(iTLM)='Tangent linear'
          label(iRPM)='Representer   '
          label(iADM)='Adjoint       '
          DO imodel=1,4
            IF (Master.and.(Csum(region,imodel,ng).gt.0.0_r8)) THEN
              WRITE (stdout,30) TRIM(label(imodel)),                    &
     &                          'model wall/CPU time profile, Grid:',   &
     &                          ng
 30           FORMAT (/,1x,a,1x,a,1x,i2.2/)
              DO iregion=0,Nregion
                IF (wall_mean(iregion,imodel).gt.0.0_r8) THEN
                  IF (iregion.eq.0) THEN
                    region_kind='total'
                  ELSE IF (iregion.eq.3) THEN
                    region_kind='io_read'
                  ELSE IF (iregion.eq.8) THEN
                    region_kind='io_write'
                  ELSE IF (iregion.ge.Mregion) THEN
                    region_kind='mpi'
                  ELSE
                    region_kind='compute'
                  END IF
                  imbalance=wall_max(iregion,imodel)/                 &
     &                      wall_mean(iregion,imodel)
                  WRITE (stdout,35) ng, imodel, iregion, region_kind,  &
     &                              calls_sum(iregion,imodel),         &
     &                              wall_min(iregion,imodel),          &
     &                              wall_mean(iregion,imodel),         &
     &                              wall_max(iregion,imodel),          &
     &                              INT(wall_max_rank(iregion,imodel)),&
     &                              cpu_min(iregion,imodel),           &
     &                              cpu_mean(iregion,imodel),          &
     &                              cpu_max(iregion,imodel), imbalance
                END IF
              END DO
            END IF
 35         FORMAT ('PROFILE_RANK grid=',i0,' model=',i0,              &
     &              ' region=',i0,' kind=',a,' calls=',f12.0,         &
     &              ' wall_min=',es15.7,' wall_mean=',es15.7,         &
     &              ' wall_max=',es15.7,' wall_max_rank=',i0,         &
     &              ' cpu_min=',es15.7,' cpu_mean=',es15.7,           &
     &              ' cpu_max=',es15.7,' imbalance=',f10.6)
            sumwall=0.0_r8
            sumcpu=0.0_r8
            sumper=0.0_r8
            DO iregion=1,Mregion-1
              IF (Csum(iregion,imodel,ng).gt.0.0_r8) THEN
                percent=100.0_r8*Csum(iregion, imodel,ng)/              &
     &                           Csum( region,MyModel,ng)
                IF (Master) WRITE (stdout,40) Pregion(iregion),         &
     &                                        Csum(iregion,imodel,ng),  &
     &                                        Csum_cpu(iregion,         &
     &                                                 imodel,ng),      &
     &                                        percent
                sumwall=sumwall+Csum(iregion,imodel,ng)
                sumcpu=sumcpu+Csum_cpu(iregion,imodel,ng)
                sumper=sumper+percent
              END IF
            END DO
 40         FORMAT (2x,a,t53,'Wall:',f14.3,2x,'CPU:',f14.3,2x,         &
     &              '(',f7.4,' %)')
            IF (Master.and.(Csum(region,imodel,ng).gt.0.0_r8)) THEN
              WRITE (stdout,50) sumwall, sumcpu, sumper
 50           FORMAT (t47,'Total Wall:',f14.3,2x,'CPU:',f14.3,2x,f8.4)
            END IF
          END DO
# ifdef DISTRIBUTE
!
!  Report elapsed time for message passage communications.
!
          DO imodel=1,4
            total=0.0_r8
            DO iregion=Mregion,Nregion
              total=total+Csum(iregion,imodel,ng)
            END DO
            IF (Master.and.(total.gt.0.0_r8)) THEN
              WRITE (stdout,30) TRIM(label(imodel)),                    &
     &                          'model message Passage profile, Grid:', &
     &                          ng
            END IF
            sumwall=0.0_r8
            sumcpu=0.0_r8
            sumper=0.0_r8
            IF (total.gt.0.0_r8) THEN
              DO iregion=Mregion,Nregion
                IF (Csum(iregion,imodel,ng).gt.0.0_r8) THEN
                  percent=100.0_r8*Csum(iregion, imodel,ng)/            &
     &                             Csum( region,Mymodel,ng)
                  IF (Master) WRITE (stdout,40) Pregion(iregion),       &
     &                                          Csum(iregion,imodel,ng),&
     &                                          Csum_cpu(iregion,       &
     &                                                   imodel,ng),    &
     &                                          percent
                  sumwall=sumwall+Csum(iregion,imodel,ng)
                  sumcpu=sumcpu+Csum_cpu(iregion,imodel,ng)
                  sumper=sumper+percent
                END IF
              END DO
              IF (Master.and.(total.gt.0.0_r8)) THEN
                WRITE (stdout,50) sumwall, sumcpu, sumper
              END IF
            END IF
          END DO
# endif
          IF (Master) WRITE (stdout,60) Csum(region,MyModel,ng),        &
     &                                  Csum_cpu(region,MyModel,ng)
  60      FORMAT (/,' All percentages use total wall time =',          &
     &            5x,f12.3,' rank-seconds',/,                          &
     &            ' Total CPU time =',20x,f12.3,' rank-seconds',/)
#endif
        END IF
!$OMP END CRITICAL (FINALIZE_WCLOCK)
      END IF
      RETURN
      END SUBROUTINE wclock_off
