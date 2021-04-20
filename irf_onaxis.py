# Imported by hand from https://github.com/gammapy/gammapy-extra/blob/master/valhalla/cta_simulation/cta_irf.py
import astropy.units as u
from astropy.io import fits
from astropy.table import Table

import gammapy

from gammapy.utils.scripts import make_path

# # Avoid deprecation Astropy warnings in gammapy.maps
import warnings
with warnings.catch_warnings():
    #from gammapy.utils.nddata import NDDataArray, BinnedDataAxis # Gammapy 0.9
    from gammapy.utils.nddata import NDDataArray
    from gammapy.maps import MapAxis
    from gammapy.irf import EffectiveAreaTable2D, EffectiveAreaTable, Background3D
    from gammapy.irf import EnergyDispersion2D, EnergyDependentMultiGaussPSF
    if (gammapy.__version__ == "0.12"):
        from gammapy.cube import make_map_exposure_true_energy, make_map_background_irf
        from gammapy.cube import PSFKernel

import numpy as np
__all__ = [
    'get_irf_components',
    'CTAIrf',
    'BgRateTable',
    'Psf68Table',
    'SensitivityTable',
    'CTAPerf_onaxis',
]
###############################################################################
def get_irf_components(self,obs_param, pointing, irfs, debug=False):

    """Get the IRf components"""

    axis = obs_param.axis
    duration = obs_param.livetime
    geom = obs_param.geom
    fov = obs_param.fov

    offset = 0*u.deg

    ### Compute the exposure map
    exposure = make_map_exposure_true_energy(
                pointing = pointing.galactic, # does not accept SkyCoord altaz
                livetime = duration,
                aeff     = irfs["aeff"],
                geom     = geom)

    ### Compute the background map
    background = make_map_background_irf(
                    pointing = pointing.galactic, # does not accept SkyCoord altaz
                    ontime   = duration,
                    bkg=irfs["bkg"],
                    geom=geom
                    )

    ### Point spread function
    psf = irfs["psf"].to_energy_dependent_table_psf(theta=offset)
    psf_kernel = PSFKernel.from_table_psf(psf, geom, max_radius=fov/2) # Why this max_radius ?

    ### Energy dispersion
    edisp = irfs["edisp"].to_energy_dispersion(offset,
                e_reco=axis.edges,
                e_true=axis.edges)

    if (debug>2):
        # Maybe this could go into a irf_plot module
        import matplotlib.pyplot as plt
        islice = 3

        exposure.slice_by_idx({"energy": islice-1}).plot(add_cbar=True)
        plt.title("Exposure map")

        background.slice_by_idx({"energy": islice}).plot(add_cbar=True)
        plt.title("Background map")

        psf_kernel.psf_kernel_map.sum_over_axes().plot(stretch="log")
        plt.title("point spread function")

        edisp.plot_matrix()
        plt.title("Energy dispersion matrix")
        plt.show()

    return exposure, background, psf_kernel, edisp
###############################################################################
#
###############################################################################
class CTAIrf(object):
    """
    CTA instrument response function container.

    Class handling CTA instrument response function.
    Written by J. Lefaucheur, July 2018
    Note : this has been for a while in gammapy 0.6 and then was removed
    For now we use the production 2 of the CTA IRF
    (https://portal.cta-observatory.org/Pages/CTA-Performance.aspx)
    adapted from the ctools
    (http://cta.irap.omp.eu/ctools/user_manual/getting_started/response.html).
    The IRF format should be compliant with the one discussed
    at http://gamma-astro-data-formats.readthedocs.io/en/latest/irfs/.
    Waiting for a new public production of the CTA IRF,
    we'll fix the missing pieces.
    This class is similar to `~gammapy.data.DataStoreObservation`,
    but only contains IRFs (no event data or livetime info).

    TODO: maybe re-factor code somehow to avoid code duplication.

    Parameters
    ----------
    aeff : `~gammapy.irf.EffectiveAreaTable2D`
        Effective area

    edisp : `~gammapy.irf.EnergyDispersion2D`
        Energy dispersion

    psf : `~gammapy.irf.EnergyDependentMultiGaussPSF`
        Point spread function

    bkg : `~gammapy.irf.Background3D`
        Background rate

    ref_sensi : `~gammapy.irf.SensitivityTable`
        Reference Sensitivity

    """


    ###########################################################################
    def __init__(self,
                 aeff =None,
                 edisp=None,
                 psf  =None,
                 bkg  =None,
                 ref_sensi=None,
                 name =None):
        self.aeff = aeff
        self.edisp = edisp
        self.psf = psf
        self.bkg = bkg
        self.ref_sensi = ref_sensi
        self.name = name

    ###########################################################################
    @classmethod
    def read(cls, filename):
        """
        Read from a FITS file.

        Parameters
        ----------
        filename : `str`
            File containing the IRFs
        """
        filename = str(make_path(filename))
        hdu_list = fits.open(filename)

        aeff = EffectiveAreaTable2D.read(filename, hdu='EFFECTIVE AREA')
        bkg = Background3D.read(filename, hdu='BACKGROUND')
        edisp = EnergyDispersion2D.read(filename, hdu='ENERGY DISPERSION')
        psf = EnergyDependentMultiGaussPSF.read(filename, hdu='POINT SPREAD FUNCTION')

        if 'SENSITIVITY' in hdu_list:
            sensi = SensitivityTable.read(filename, hdu='SENSITIVITY')
        else:
            sensi = None

        return cls(
            aeff=aeff,
            bkg=bkg,
            edisp=edisp,
            psf=psf,
            ref_sensi=sensi,
            name = filename
        )

###############################################################################
#
###############################################################################
class BgRateTable(object):
    """
    Background rate table.

    The IRF format should be compliant with the one discussed
    at http://gamma-astro-data-formats.readthedocs.io/en/latest/irfs/.
    Work will be done to fix this.
    Parameters
    ----------
    energy_lo, energy_hi : `~astropy.units.Quantity`, `~gammapy.utils.nddata.BinnedDataAxis`
        Bin edges of energy axis

    data : `~astropy.units.Quantity`
        Background rate

    """

    ###########################################################################
    def __init__(self, energy_lo, energy_hi, data):
        #axes = [
        #    BinnedDataAxis(energy_lo, energy_hi, interpolation_mode='log', name='energy'),
        #]

        edges = np.append(energy_lo.value,energy_hi[-1].value)*energy_lo.unit
        axes = [
            MapAxis(edges, interp='log', name='energy',node_type='edges',unit='TeV')
        ]
        #print("BgRateTable ",axes)
        self.data = NDDataArray(axes=axes, data=data)

    ###########################################################################
    @property
    def energy(self):
        return self.data.axes[0]

    ###########################################################################
    @classmethod
    def from_table(cls, table):
        """Background rate reader"""
        energy_lo = table['ENERG_LO'].quantity
        energy_hi = table['ENERG_HI'].quantity
        data = table['BGD'].quantity
        return cls(energy_lo=energy_lo, energy_hi=energy_hi, data=data)

    ###########################################################################
    @classmethod
    def from_hdulist(cls, hdulist, hdu='BACKGROUND'):
        fits_table = hdulist[hdu]
        table = Table.read(fits_table)
        return cls.from_table(table)

    ###########################################################################
    @classmethod
    def read(cls, filename, hdu='BACKGROUND'):
        filename = make_path(filename)
        with fits.open(str(filename), memmap=False) as hdulist:
            return cls.from_hdulist(hdulist, hdu=hdu)

    ###########################################################################
    def plot(self, ax=None, energy=None, **kwargs):
        """
        Plot background rate.

        Parameters
        ----------
        ax : `~matplotlib.axes.Axes`, optional
            Axis

        energy : `~astropy.units.Quantity`
            Energy nodes

        Returns
        -------
        ax : `~matplotlib.axes.Axes`
            Axis

        """
        import matplotlib.pyplot as plt
        ax = plt.gca() if ax is None else ax

        energy = energy or self.energy.nodes
        values = self.data.evaluate(energy=energy)
        xerr = (
            energy.value - self.energy.lo.value,
            self.energy.hi.value - energy.value,
        )
        ax.errorbar(energy.value, values.value, xerr=xerr, fmt='o', **kwargs)
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_xlabel('Energy [{}]'.format(self.energy.unit))
        ax.set_ylabel('Background rate [{}]'.format(self.data.data.unit))

        return ax


###############################################################################
#
###############################################################################
class Psf68Table(object):
    """
    Background rate table.

    The IRF format should be compliant with the one discussed
    at http://gamma-astro-data-formats.readthedocs.io/en/latest/irfs/.
    Work will be done to fix this.
    Parameters
    -----------
    energy_lo, energy_hi : `~astropy.units.Quantity`, `~gammapy.utils.nddata.BinnedDataAxis`
        Bin edges of energy axis

    data : `~astropy.units.Quantity`
        Background rate

    """

    ###########################################################################
    def __init__(self, energy_lo, energy_hi, data):
        #axes = [
        #    BinnedDataAxis(energy_lo, energy_hi, interpolation_mode='log', name='energy'),
        #]
        edges = np.append(energy_lo.value,energy_hi[-1].value)*energy_lo.unit
        axes = [
            MapAxis(edges, interp='log', name='energy',node_type='edges',unit='TeV'),
        ]
        #print("PSF68Table ",axes)
        self.data = NDDataArray(axes=axes, data=data)

    ###########################################################################
    @property
    def energy(self):
        return self.data.axes[0]

    ###########################################################################
    @classmethod
    def from_table(cls, table):
        """PSF reader"""
        energy_lo = table['ENERG_LO'].quantity
        energy_hi = table['ENERG_HI'].quantity
        data = table['PSF68'].quantity
        return cls(energy_lo=energy_lo, energy_hi=energy_hi, data=data)

    ###########################################################################
    @classmethod
    def from_hdulist(cls, hdulist, hdu='POINT SPREAD FUNCTION'):
        fits_table = hdulist[hdu]
        table = Table.read(fits_table)
        return cls.from_table(table)

    ###########################################################################
    @classmethod
    def read(cls, filename, hdu='POINT SPREAD FUNCTION'):
        filename = make_path(filename)
        with fits.open(str(filename), memmap=False) as hdulist:
            return cls.from_hdulist(hdulist, hdu=hdu)

    ###########################################################################
    def plot(self, ax=None, energy=None, **kwargs):
        """
        Plot point spread function.

        Parameters
        ----------
        ax : `~matplotlib.axes.Axes`, optional
            Axis

        energy : `~astropy.units.Quantity`
            Energy nodes

        Returns
        -------
        ax : `~matplotlib.axes.Axes`
            Axis

        """
        import matplotlib.pyplot as plt
        ax = plt.gca() if ax is None else ax

        energy = energy or self.energy.nodes
        values = self.data.evaluate(energy=energy)
        xerr = (
            energy.value - self.energy.lo.value,
            self.energy.hi.value - energy.value,
        )
        ax.errorbar(energy.value, values.value, xerr=xerr, fmt='o', **kwargs)
        ax.set_xscale('log')
        ax.set_xlabel('Energy [{}]'.format(self.energy.unit))
        ax.set_ylabel(
            'Angular resolution 68 % containment [{}]'.format(self.data.data.unit)
        )

        return ax


###############################################################################
#
###############################################################################
class SensitivityTable(object):
    """
    Sensitivity table.

    The IRF format should be compliant with the one discussed
    at http://gamma-astro-data-formats.readthedocs.io/en/latest/irfs/.
    Work will be done to fix this.

    Parameters
    -----------
    energy_lo, energy_hi : `~astropy.units.Quantity`, `~gammapy.utils.nddata.BinnedDataAxis`
        Bin edges of energy axis

    data : `~astropy.units.Quantity`
        Sensitivity

    """

    ###########################################################################
    def __init__(self, energy_lo, energy_hi, data):
        #axes = [
        #    BinnedDataAxis(energy_lo, energy_hi, interpolation_mode='log', name='energy'),
        #]
        edges = np.append(energy_lo.value,energy_hi[-1].value)*energy_lo.unit
        axes = [MapAxis(edges, interp='log', name='energy',node_type='edges',unit='TeV')]
        self.data = NDDataArray(axes=axes, data=data)
        # print("Sensitivity ",axes)

    ###########################################################################
    @property
    def energy(self):
        return self.data.axis('energy')

    ###########################################################################
    @classmethod
    def from_table(cls, table):
        energy_lo = table['ENERG_LO'].quantity
        energy_hi = table['ENERG_HI'].quantity
        data = table['SENSITIVITY'].quantity
        return cls(energy_lo=energy_lo, energy_hi=energy_hi, data=data)

    ###########################################################################
    @classmethod
    def from_hdulist(cls, hdulist, hdu='SENSITIVITY'):
        fits_table = hdulist[hdu]
        table = Table.read(fits_table)
        return cls.from_table(table)

    ###########################################################################
    @classmethod
    def read(cls, filename, hdu='SENSITVITY'):
        filename = make_path(filename)
        with fits.open(str(filename), memmap=False) as hdulist:
            return cls.from_hdulist(hdulist, hdu=hdu)

    ###########################################################################
    def plot(self, ax=None, energy=None, **kwargs):
        """
        Plot sensitivity.

        Parameters
        ----------
        ax : `~matplotlib.axes.Axes`, optional
            Axis

        energy : `~astropy.units.Quantity`
            Energy nodes

        Returns
        -------
        ax : `~matplotlib.axes.Axes`
            Axis

        """
        import matplotlib.pyplot as plt
        ax = plt.gca() if ax is None else ax

        energy = energy or self.energy.nodes
        values = self.data.evaluate(energy=energy)
        xerr = (
            energy.value - self.energy.lo.value,
            self.energy.hi.value - energy.value,
        )
        ax.errorbar(energy.value, values.value, xerr=xerr, fmt='o', **kwargs)
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_xlabel('Reco Energy [{}]'.format(self.energy.unit))
        ax.set_ylabel('Sensitivity [{}]'.format(self.data.data.unit))

        return ax


###############################################################################
#
###############################################################################
class CTAPerf_onaxis(object):
    """
    CTA instrument response function container.

    Class handling CTA performance.
    For now we use the production 2 of the CTA IRF
    (https://portal.cta-observatory.org/Pages/CTA-Performance.aspx)
    The IRF format should be compliant with the one discussed
    at http://gamma-astro-data-formats.readthedocs.io/en/latest/irfs/.
    Work will be done to handle better the PSF and the background rate.
    This class is similar to `~gammapy.data.DataStoreObservation`,
    but only contains performance (no event data or livetime info).
    TODO: maybe re-factor code somehow to avoid code duplication.
    Parameters
    ----------
    aeff : `~gammapy.irf.EffectiveAreaTable`
        Effective area

    edisp : `~gammapy.irf.EnergyDispersion2D`
        Energy dispersion

    psf : `~gammapy.scripts.Psf68Table`
        Point spread function

    bkg : `~gammapy.scripts.BgRateTable`
        Background rate

    sens : `~gammapy.scripts.SensitivityTable`
        Sensitivity

    rmf: `~gammapy.irf.EnergyDispersion`
        RMF

    """

    ###########################################################################
    def __init__(self, aeff=None, edisp=None, psf=None,
                 bkg=None, sens=None, rmf=None, name=None):
        self.aeff = aeff
        self.edisp = edisp
        self.psf = psf
        self.bkg = bkg
        self.sens = sens
        self.rmf = rmf
        self.name = name

    ###########################################################################
    @classmethod
    def read(cls, filename, offset='0.5 deg'):
        """
        Read from a FITS file.

        Compute RMF at 0.5 deg offset on fly.
        Parameters
        ----------
        filename : `str`
            File containing the IRFs

        """
        filename = str(make_path(filename))

        with fits.open(filename, memmap=False) as hdulist:
            aeff = EffectiveAreaTable.from_hdulist(hdulist=hdulist)
            edisp = EnergyDispersion2D.read(filename, hdu='ENERGY DISPERSION')
            bkg = BgRateTable.from_hdulist(hdulist=hdulist)
            psf = Psf68Table.from_hdulist(hdulist=hdulist)
            sens = SensitivityTable.from_hdulist(hdulist=hdulist)

        # Create rmf with appropriate dimensions (e_reco->bkg, e_true->area)
        #e_reco_min = bkg.energy.lo[0]
        #e_reco_max = bkg.energy.hi[-1]
        #e_reco_bin = bkg.energy.nbins
        #e_reco_axis = EnergyBounds.equal_log_spacing(
        #    e_reco_min, e_reco_max, e_reco_bin, 'TeV',
        #)
        e_reco_axis = bkg.data.axis("energy").edges
        # print("e_reco_axus",e_reco_axis)

#        e_true_min = aeff.energy.lo[0]
#        e_true_max = aeff.energy.hi[-1]
#        e_true_bin = aeff.energy.nbins
#        e_true_axis = EnergyBounds.equal_log_spacing(
#            e_true_min, e_true_max, e_true_bin, 'TeV',
#        )
        if (gammapy.__version__ == "0.12"):
            e_true_axis = aeff.data.axis("energy").edges
        if (gammapy.__version__ == "0.17"):
            e_true_axis = aeff.data.axis("energy_true").edges

        rmf = edisp.to_energy_dispersion(
            offset=offset, e_reco=e_reco_axis, e_true=e_true_axis,
        )

        return cls(
            aeff=aeff,
            bkg=bkg,
            edisp=edisp,
            psf=psf,
            sens=sens,
            rmf=rmf,
            name=filename
        )

    ###########################################################################
    def peek(self, figsize=(15, 8)):
        """Quick-look summary plots."""
        import matplotlib.pyplot as plt

        fig = plt.figure(figsize=figsize)
        ax_bkg = plt.subplot2grid((2, 4), (0, 0))
        ax_area = plt.subplot2grid((2, 4), (0, 1))
        ax_sens = plt.subplot2grid((2, 4), (0, 2), colspan=2, rowspan=2)
        ax_psf = plt.subplot2grid((2, 4), (1, 0))
        ax_resol = plt.subplot2grid((2, 4), (1, 1))

        self.bkg.plot(ax=ax_bkg)
        self.aeff.plot(ax=ax_area).set_yscale('log')
        self.sens.plot(ax=ax_sens)
        self.psf.plot(ax=ax_psf)
        self.edisp.plot_bias(ax=ax_resol, offset='0.5 deg')

        ax_bkg.grid(which='both')
        ax_area.grid(which='both')
        ax_sens.grid(which='both')
        ax_psf.grid(which='both')
        fig.tight_layout()

    ###########################################################################
    @staticmethod
    def superpose_perf(cta_perf, labels):
        """
        Superpose performance plot.

        Parameters
        ----------
        cta_perf : `list` of `~gammapy.scripts.CTAPerf`
           List of performance

        labels : `list` of `str`
           List of labels

        """

        import matplotlib.pyplot as plt

        fig = plt.figure(figsize=(10, 8))
        ax_bkg = plt.subplot2grid((2, 2), (0, 0))
        ax_area = plt.subplot2grid((2, 2), (0, 1))
        ax_psf = plt.subplot2grid((2, 2), (1, 0))
        ax_sens = plt.subplot2grid((2, 2), (1, 1))

        for index, (perf, label) in enumerate(zip(cta_perf, labels)):
            plot_label = {'label': label}
            perf.bkg.plot(ax=ax_bkg, **plot_label)
            perf.aeff.plot(ax=ax_area, **plot_label).set_yscale('log')
            perf.sens.plot(ax=ax_sens, **plot_label)
            perf.psf.plot(ax=ax_psf, **plot_label)

        ax_bkg.legend(loc='best')
        ax_area.legend(loc='best')
        ax_psf.legend(loc='best')
        ax_sens.legend(loc='best')

        ax_bkg.grid(which='both')
        ax_area.grid(which='both')
        ax_psf.grid(which='both')
        ax_sens.grid(which='both')

        fig.tight_layout()
