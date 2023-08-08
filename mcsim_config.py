# -*- coding: utf-8 -*-
"""
Created on Mon Feb  3 08:58:16 2020

@author: Stolar

This modules contains the parameters of the simulation handled
by :file:`mcsim.py`.

"""
import astropy.units as u
import numpy as np

__all__ = ["generate_E_edges", "nLiMamin", "on_size", "offset", "erec_sparse",
           "erec_spectral", "erec_edges","erec_min","erec_max"]

nLiMamin    = 10
"""
Count number below which Li&Ma cannot be trusted anymore
"""

containment = 0.68
"""
Containment : the fraction of the background area corresponding to on/off regions
"""

on_size     = { "FullArray"        : 0.4*u.deg,
                "4LSTs09MSTs"      : 0.4*u.deg,
                "LST"              : 0.4*u.deg,
                "MST"              : 0.25*u.deg,
                "14MSTs37SSTs"     : 0.25*u.deg,
                "4LSTs14MSTs40SSTs": 0.4*u.deg,} # On region size, was 0.2
"""
The on (and off-) region radius
"""

offset      = { "FullArray"        : 0.75*u.deg,
                "4LSTs09MSTs"      : 0.75*u.deg,
                "LST"              : 0.75*u.deg,
                "MST"              : 0.5*u.deg,
                "14MSTs37SSTs"     : 0.5*u.deg,
                "4LSTs14MSTs40SSTs": 0.75*u.deg,
                }
"""
the on and off region distances to the center of the field of view
(Should be greater than the on-size radius)
"""




erec_sparse  = np.asarray([30, 40, 60, 110, 200, 350, 700,
                         1300, 2400, 4400, 8000, 15000])*u.GeV
"""
This spacing was generated by hand from the output of the function
:func:`mcsim.generate_E_edges`. It ensures that the critical IRF thresholds are
in the list for an efficient masking.

Warning: an axis starting below the minimal generated energy creates problem
in the background evaluation.
"""

erec_spectral = np.asarray([  30.,   40.,   50.,   60.,   80.,  110.,  160., \
                             200.,  250.,  350.,  400.,  530.,  670.,  850., \
                            1082., 1374., 1745., 2216., 2815., 3575., 4540., \
                            5766.,  7323., 9300., 11811.,  15000.])*u.GeV
"""
This is a denser E-binning suitable for spectral analysis.
"""

erec_edges = {
"FullArray"        : erec_spectral, # Omega
"4LSTs09MSTs"      : erec_spectral, # Alpha
"LST"              : erec_spectral,
"MST"              : erec_spectral,
"14MSTs37SSTs"     : erec_spectral, # Alpha
"4LSTs14MSTs40SSTs": erec_spectral  # Beta
}
"""
The reconstructed energy bins for each subarray.
"""

safe_margin = 1*u.GeV
erec_min = {"FullArray"         : {"20deg":  30*u.GeV -safe_margin,
                                   "40deg":  40*u.GeV -safe_margin,
                                   "60deg": 110*u.GeV -safe_margin
                                  },
            "4LSTs09MSTs"       : {"20deg":  30*u.GeV -safe_margin,
                                   "40deg":  40*u.GeV -safe_margin,
                                   "60deg": 110*u.GeV -safe_margin
                                  },
             "LST"              : {"20deg":  30*u.GeV -safe_margin,
                                   "40deg":  40*u.GeV -safe_margin,
                                   "60deg": 110*u.GeV -safe_margin
                                  },
             "MST"              : {"20deg":  60*u.GeV -safe_margin, # was 110
                                   "40deg":  60*u.GeV -safe_margin, # was 110
                                   "60deg": 200*u.GeV -safe_margin
                                  },
             "14MSTs37SSTs"     : {"20deg":  60*u.GeV -safe_margin, # was 110
                                   "40deg": 110*u.GeV -safe_margin, # was 110
                                   "60deg": 350*u.GeV -safe_margin
                                  },
             "4LSTs14MSTs40SSTs": {"20deg":  30*u.GeV -safe_margin, # was 110
                                   "40deg":  40*u.GeV -safe_margin, # was 110
                                   "60deg": 110*u.GeV -safe_margin
                                   }
             }
"""
The minimal reconstructed energies for each subarrays and IRF zenith angles.
"""
erec_max = {"20deg": 10*u.TeV + safe_margin,
            "40deg": 10*u.TeV + safe_margin,
            "60deg": 10*u.TeV + safe_margin}

"""
The maximal reconstructed energies for each IRF zenith angles.
"""

#------------------------------------------------------------------------------
def generate_E_edges(E1 = 10*u.GeV, E2 = 100*u.TeV,
                     subarray="FullArray", nperdecade=4):

    """
    Generate energy edges including the reconstructed energy thresholds.
    Just copy the output to the code and rearrange the values to remove too
    narrow bins.

    Parameters
    ----------
    E1 : Quantity, optional
        Lower bound. The default is 10*u.GeV.
    E2 : Quantity, optional
        Upper bound. The default is 100*u.TeV.
    subarray: string
        Subarray keyword. The default is "FullArray"
    nperdecade : Integer, optional
        Default number of bins per decade. The default is 4.

    Returns
    -------
    None.

    """
    unit_ref = E1.unit
    Emin = E1.to(unit_ref).value
    Emax = E2.to(unit_ref).value

    # Compute the number of bins to be generated from the number of decades
    ndecade = np.log10(Emax/Emin) # Number of decades covered

    nbin = ndecade*nperdecade
    print(" ARRAY  : ",subarray)
    print("Total number of bins =",nbin)

    e_edges = np.logspace(np.log10(Emin),np.log10(Emax),int(nbin+1))*unit_ref
    print("Initial edging :")
    print(e_edges)

    # Add critical values to the array
    e_critical = [e.to(unit_ref).value for e in erec_min[subarray].values()]*unit_ref
    e_edges = np.append(e_edges, e_critical)
    e_critical = [e.to(unit_ref).value for e in erec_max.values()]*unit_ref
    e_edges = np.append(e_edges, e_critical)

    print("Final edging - indicative (copy this and rearrange if needed):")
    print(e_edges)


###############################################################################
if __name__ == "__main__":

    generate_E_edges(E1=30*u.GeV,E2=15*u.TeV,nperdecade=10)
