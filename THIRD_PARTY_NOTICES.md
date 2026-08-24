# Third-party notices

The root [MIT License](LICENSE) covers contributions and modifications made by the SYSU MCC Team. It does not replace the copyright, license, attribution, or citation requirements of third-party material bundled in this repository.

## ROMS/TOMS

The Regional Ocean Modeling System / Terrain-following Ocean Modeling System source is copyright © 2002–2017 The ROMS/TOMS Group and is distributed under its MIT/X-style license. The complete bundled notice is available at [`ROMS_CoSiNE15/ROMS/License_ROMS.txt`](ROMS_CoSiNE15/ROMS/License_ROMS.txt).

The ROMS/TOMS Group asks users to acknowledge the group, individual developers, participating institutions, agencies, and relevant ROMS publications.

## CoSiNE ecosystem model

The bundled UMaine CoSiNE implementation is integrated into the ROMS source tree and retains the copyright and license headers in its source files. In particular, see [`bio_UMAINE15.h`](ROMS_CoSiNE15/ROMS/Nonlinear/Biology/bio_UMAINE15.h).

The source requests citation of:

- Chai, F., Dugdale, R. C., Peng, T.-H., Wilkerson, F. P., and Barber, R. T. (2002). One dimensional ecosystem model of the equatorial Pacific upwelling system, Part I: Model development and silicon and nitrogen cycle. *Deep-Sea Research Part II*, 49(13–14), 2713–2745.
- Xiu, P., and Chai, F. (2011). Modeled biogeochemical responses to mesoscale eddies in the South China Sea. *Journal of Geophysical Research*, 116, C10006. https://doi.org/10.1029/2010JC006800

The source also records adaptation and development by Fei Chai, Lei Shi, Feng Zhou, Peng Xiu, and Qicheng Meng. Refer to the file headers for the complete provenance attached to individual routines.

## Modeling Coupling Toolkit (MCT)

The bundled Modeling Coupling Toolkit is copyright © 2005 University of Chicago as Operator of Argonne National Laboratory. Its redistribution conditions, warranty disclaimer, limitation of liability, and required acknowledgment are preserved in [`ROMS_CoSiNE15/Lib/MCT/COPYRIGHT`](ROMS_CoSiNE15/Lib/MCT/COPYRIGHT).

Required acknowledgment:

> This product includes software developed by the University of Chicago, as Operator of Argonne National Laboratory.

## ARPACK/PARPACK

The repository contains an ARPACK/PARPACK distribution and ROMS-side checkpointing modifications under [`ROMS_CoSiNE15/Lib/ARPACK`](ROMS_CoSiNE15/Lib/ARPACK). The bundled README attributes ARPACK to its original authors, including Danny Sorensen and Richard Lehoucq. Redistribution is subject to the applicable Netlib terms; see the [Netlib license](https://netlib.org/math/license.html) and retain upstream notices when redistributing source or binaries.

## User responsibility

Input datasets are not distributed in this repository. Users are responsible for complying with the licenses and citation requirements of their own grids, forcing, boundary, initial-condition, observational, and reference datasets.
