#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 4
#SBATCH -n 128  
#SBATCH --exclusive
##SBATCH --gres=dcu:1 
#SBATCH --exclusive
ulimit -s unlimited
ulimit -l unlimited
module purge
module load   mathlib/netcdf/4.4.1/intel  mpi/hpcx/2.7.4/intel-2017.5.239  mathlib/hdf5/1.8.20/intel compiler/intel/2017.5.239 

rm log_SCS_Dongsha60_2021_daily.txt

cp ./Inputfiles/SCS/roms_frc_tide_SCS_org.nc ./Inputfiles/SCS/roms_frc_tide_SCS_org.nc
mpirun  -np 128 ./oceanM ROMS/External/ocean_SCS_Dongsha60_bio15.in > log_SCS_Dongsha60_2021_daily.txt

