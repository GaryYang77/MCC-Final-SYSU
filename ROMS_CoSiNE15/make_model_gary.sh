make -j1 \
  ROMS_APPLICATION=BYE24BIO15 \
  FORT=gfortran \
  FC=/usr/bin/gfortran \
  USE_MPI=on \
  USE_MPIF90= \
  USE_NETCDF4=on \
  NF_CONFIG=/usr/bin/nf-config \
  NETCDF_INCDIR=/usr/include \
  SCRATCH_DIR="$LAB_ROOT/builds/mcc_gfortran" \
  BINDIR="$LAB_ROOT/bin" \
  LD=/usr/bin/gfortran \
  FFLAGS="-frepack-arrays -O2 -ffast-math -fallow-argument-mismatch -ffree-line-length-none -I/usr/include/x86_64-linux-gnu/mpich" \
  LIBS="-L/usr/lib/x86_64-linux-gnu -lnetcdff -lnetcdf -lmpichfort -lmpich"
