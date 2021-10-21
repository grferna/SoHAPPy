"""
* Create a GRB list to be analysed from the config file or the command line (:func:`init`)


seed= 'random-seed'
Advanced usage:
In SoHappy.py, change warnings.filterwarnings('ignore') into
warnings.filterwarnings('error') to have the code stopped in case of warning,
and be able to identify its origin.
The 'ignore' option is motivated by to warning in astropy (deprecation or
too distant dates).

"""
from __init__ import __version__

import os
import sys

from   mcsim  import MonteCarlo

os.environ['GAMMAPY_EXTRA'] =r'../input/gammapy-extra-master'
os.environ['GAMMAPY_DATA'] =r'../input/gammapy-extra-master/datasets'
#print(os.getenv('GAMMAPY_EXTRA'))
#print(os.listdir(os.getenv('GAMMAPY_EXTRA')))

# Transform warnings into errors - useful to find who is guilty !
import warnings
#warnings.filterwarnings('error')
warnings.filterwarnings('ignore')

import numpy as np
import time

from   datetime import datetime
from   pathlib  import Path
import astropy.units as u

from grb            import GammaRayBurst
from timeslot       import Slot
from configuration import Configuration

import mcsim_res  as mcres
from utilities    import Log

# Do not refresh IERS data
from astropy.utils import iers
iers.conf.auto_download = False

# For refreshing
# print(" Refreshing IERS")
# from astroplan import download_IERS_A
# download_IERS_A
# print(" ->Done")

__all__ = ["main", "get_grb_fromfile", "get_delay"]

###############################################################################
def welcome(log):
    import gammapy

    log.prt(datetime.now())
    log.prt("+----------------------------------------------------------------+")
    log.prt("|                                                                |")
    log.prt("|                    SoHAPPy with GammaPy {:8s}               |"
          .format(gammapy.__version__))
    log.prt("|                            ({:8s})                          |"
          .format(__version__))
    log.prt("|  (Simulation of High-energy Astrophysics Processes in Python)  |")
    log.prt("|                                                                |")
    log.prt("+----------------------------------------------------------------+")
    
    return
###############################################################################
def get_grb_fromfile(item, 
                     config = None,
                     grb_folder  = None, 
                     log = None):
    """
    Obtain data for the ith GRB file and create a GammaRayBurst instance.

    Parameters
    ----------
    i : integer
        GRB position in the list
    prompt : boolen, optional
        If True, reads the prompt GRB file, otherwise the afterglow (default).
    afterglow : boolean, optional
        If True, use the afterglow file generic information (e.g.) for the
        prompt data, oterwise use the default.
        The default is False.
    log : TextIO, optional
        Log file. The default is None.

    Returns
    -------
    grb : GammaRayBurst
        A GammaRayBurst instance

    """
    
    if config == None:
        test_prompt = False 
        eblmodel    = None
        magnify     = 1
        afterglow   = False 
    else:
        test_prompt = config.test_prompt
        eblmodel    = config.EBLmodel
        magnify     = config.magnify
        afterglow   = config.use_afterglow
    
    if not test_prompt: # Normal case : afterglow
        if isinstance(item, str):
            # this is a GRB name string
            filename = Path(grb_folder
                            + "historical/GRB_"
                            + item +".yml")
            import yaml
            from yaml.loader import SafeLoader
            with open(filename) as f:
                data = yaml.load(f, Loader=SafeLoader)
                grb  = GammaRayBurst.from_yaml(data,ebl=eblmodel)
        elif isinstance(item, int):
            filename = Path(grb_folder
                            + "LONG_FITS/"
                            + "Event"
                            + str(item)+".fits")
            grb = GammaRayBurst.from_fits(filename,
                                     ebl     = eblmodel,
                                     magnify = magnify)
    else: # Special case for prompt
        # create a new object from the default (Visible in North)
        loc = Path('../input/lightcurves/prompt'
                   + "/events_"+str(item)+".fits")
        if (afterglow):
            # use afterglow characteristics
            loc_glow = Path(grb_folder + "/Event"+str(item)+".fits")
            glow = GammaRayBurst.from_fits(loc_glow, ebl = eblmodel)
            grb = GammaRayBurst.read_prompt(loc,
                                            glow=glow,
                                            ebl = eblmodel,
                                            magnify = magnify)
        else:
            # use default visibility
            sys.exit(" Redshift should be provided")
            grb = GammaRayBurst.read_prompt(loc,
                                            glow=None,
                                            ebl = eblmodel,
                                            z   = None,
                                            magnify = magnify)

    return grb

###############################################################################
def get_delay(dtslew,fixslew,dtswift,fixswift):
    """
    Compute the overall delay to be applied to the start of detection
    (satellite and telescope slewing), according to the user parameters.

    Returns
    -------
    dt : Quantity (time)
        Delay before the detection can start.

    """
    delay = {"North":0*u.s, "South":0*u.s}

    for loc in ["North", "South"]:

        dt = 0*u.s
        if (fixslew):  dt = dtslew[loc]
        else:          dt = dtslew[loc]*np.random.random()

        if (fixswift): dt = dt + dtswift # don't do += !!!
        else: sys.exit("Variable SWIFT delay not implemented)")
        delay[loc] = dt.to(u.s)

    return delay

###############################################################################
def main(argv):
    """
    1. Manage input/output
        - GRB data identifier list
        - open output simulation and log files

    2. Loop over input identifier list
        - get GRB data from the identifier
        - create original time slot form the GRB data
        - update vibilities in N and S if requested
        - save GRB if requested
        - Check individual sites (N and S)
            - Create a MC object
            - Modify the time slot fopr the visibility including the delays
            - If GRB is still vsisible:
                - Dress the GRB slot with physics (IRF and spectra)
                - Run the simulation
            - Display results even if not visible
        - Check the N+S case if GRB visible on both sites
            - Create a MC object
            - Modify the time slot fopr the visibility including the delays
            - Dress the GRB slot with physics (IRF and spectra)
            - Run the simulation
            - Display results

    3. Close files, terminate

    Parameters
    ----------
    argv : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    
    # Change gammapy logging to avoid warning messages 
    import logging
    logging.basicConfig()
    log = logging.getLogger("gammapy.irf")
    log.setLevel(logging.ERROR)   
    
    # Read Configuration - (create output folder)
    cf = Configuration(sys.argv[1:])
    cf.create_output_folder() # Create output folder
    
    sim_filename    = Path(cf.res_dir, cf.datafile)
    log_filename    = Path(cf.res_dir, cf.logfile)
    log = Log(name  = log_filename, talk=not cf.silent)    
    
    # Print welcome message and configuration summary
    welcome(log)
    cf.print(log)
    
    # Backup configuration to output folder
    cf.write()
    
    # Check if something can be analysed
    if (cf.ngrb<=0):
        print(" NO ANALYSIS REQUIRED (ngrb<=0)")
        sys.exit(2)

    # Prepare expert output file for individual slices
    if (cf.write_slices): dump_dir = cf.res_dir
    else: dump_dir = None
    
    # Start chronometer
    start_all = time.time() # Starts chronometer #1

    # GRB list to be analysed
    if type(cf.ifirst)!=list:
        if isinstance(cf.ifirst,str):
            grblist = [cf.ifirst]
        elif isinstance(cf.ifirst, int):
            grblist = list(range(cf.ifirst,cf.ifirst+cf.ngrb))
            first = str(cf.ifirst)
    else:
        grblist = cf.ifirst
        first = str(grblist[0])

    start_pop = time.time() # Start chronometer #2

    with open(sim_filename, 'w') as pop:

        ##############################
        # Loop over GRB population   #
        ##############################

        mcres.welcome(cf.arrays,log=log) # Remind simulation parameters

        first = True # Actions for first GRB only
        for item in grblist:

            ### Get GRB
            grb = get_grb_fromfile(item,
                                   config = cf,
                                   grb_folder = cf.grb_dir,
                                   log = log) 
            
            # Create original slot (slices) and fix observation points
            origin = Slot(grb,
                          opt   = cf.obs_point,
                          name  = grb.name,
                          debug = bool(cf.dbg>1))

            # Recompute visbility windows if requested
            from visibility import Visibility

            for loc in ["North","South"]:

                if (cf.vis_dir != None):
                    name = Path(cf.vis_dir,grb.name+"_"+loc+"_vis.bin")
                    grb.vis[loc] = Visibility.read(name)
                elif (cf.vis_cmp):
                    grb.vis[loc] = Visibility.compute(grb,
                                         loc,
                                         observatory = cf.observatory,
                                         altmin      = cf.altmin,
                                         altmoon     = cf.altmoon,
                                         moondist    = cf.moondist,
                                         moonlight   = cf.moonlight,
                                         depth       = cf.depth,
                                         skip        = cf.skip,
                                         force_vis   = cf.forced_visible,
                                         debug       = bool(cf.dbg>2))

            # Printout grb and visibility windows
            if cf.niter<=1 or cf.dbg>0 or cf.ngrb==1 :
                log.prt(grb)
                grb.vis["North"].print(log=log)
                grb.vis["South"].print(log=log)

            # Plot grb spectra and lightcurve and visibility windows
            if (cf.show >0):
                import grb_plot     as gplt
                gplt.spectra(grb,opt="Packed")
                gplt.visibility_plot(grb, loc ="North")
                gplt.visibility_plot(grb, loc ="South")

                gplt.pause()

                if (cf.dbg>2) :
                    gplt.animated_spectra(grb,savefig=True,outdir=cf.res_dir)

                #plt.show(block=True)

            # Save GRB to file if requested
            if (cf.save_grb): grb.write(cf.res_dir)

            ###--------------------------------------------###
            #  Check individual sites - Loop over locations
            ###--------------------------------------------###
            for loc in grb.site_keys:

                name = grb.name + "-" + loc

                log.banner(" SIMULATION  : {:<50s} ".format(name))
                # Create a MC object
                mc = MonteCarlo(niter     = cf.niter,
                                method    = cf.method,
                                fluctuate = cf.do_fluctuate,
                                nosignal  = cf.signal_to_zero,
                                seed      = cf.seed,
                                debug     = cf.dbg,
                                name      = name)

                # If visible, run simulation
                if grb.vis[loc].vis_tonight:
                    slot = origin.copy(name="loc")

                    # Simulate delay
                    delay = get_delay(cf.dtslew, cf.fixslew,
                                      cf.dtswift, cf.fixswift)
                    still_vis = slot.apply_visibility(delay = delay[loc],
                                                      site  = loc)

                    # If still visible add IRF feature and run
                    if (still_vis):
                        slot.dress(irf_dir = cf.irf_dir,
                                   arrays  = cf.arrays,
                                   zenith  = cf.fixed_zenith)
                        if (cf.dbg > 2): print(slot)

                        mc.run(slot,boost    = cf.do_accelerate,
                                    savedset = cf.save_dataset,
                                    dump_dir = dump_dir)

                # Get information and results even if not visible
                first = mcres.result(mc, grb, log=log, header=first, pop=pop)

                # If Simulation was not aborted, plot some results
                if (mc.err == mc.niter) and (cf.show > 0):
                    slot.plot()
                    import mcsim_plot as mplt
                    mplt.show(mc,loc=loc)

                # If requested save simulation to disk
                if (cf.save_simu):
                    mc.write(Path(cf.res_dir,name + "_sim.bin"))

            ###--------------------------------------------###
            #   Check GRB seen on both sites
            ###--------------------------------------------###
            name = grb.name + "-Both"

            # Create a MC object
            log.banner(" SIMULATION  : {:<50s} ".format(name))
            mc = MonteCarlo(niter     = cf.niter,
                            method    = cf.method,
                            fluctuate = cf.do_fluctuate,
                            nosignal  = cf.signal_to_zero,
                            seed      = cf.seed,
                            debug     = cf.dbg,
                            name      = name)

            # If visible on both sites, run simulation
            if grb.vis["North"].vis_tonight and grb.vis["South"].vis_tonight:

                slot = origin.both_sites(delay  = delay,
                                         debug  = (cf.dbg>1))
                if (slot != None):
                    slot.dress(irf_dir = cf.irf_dir,
                               arrays  = cf.arrays,
                               zenith  = cf.fixed_zenith)
                    if (cf.dbg > 2): print(slot)

                    mc.run(slot,boost    = cf.do_accelerate,
                                savedset = cf.save_dataset,
                                dump_dir = dump_dir)

            # Get information and results even if not visible
            first= mcres.result(mc, grb, log=log, header=first, pop = pop)

            # If simulation was not aborted, plot some results
            if (mc.err == mc.niter) and (cf.show > 0):
                if (cf.show>0):
                    slot.plot()
                import mcsim_plot as mplt
                mplt.show(mc,loc="Both")

            # If requested save simulation to disk
            if (cf.save_simu): mc.write(Path(cf.res_dir,name + "_sim.bin"))

        # END of Loop over GRB

    # Stop chronometer
    end_pop = time.time()
    end_all = time.time()
    elapsed = end_pop-start_pop

    log.prt("\n-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*")
    log.prt(" Duration   = {:8.2f} (s)".format(elapsed))
    log.prt("  per GRB   = {:8.2f} (s)".format( (elapsed)/cf.ngrb))
    log.prt("  per trial = {:8.3f} (s)".format( (elapsed)/cf.ngrb/cf.niter))
    log.prt("-*-*-*-*-*-*-*-*- End of population simulation -*-*-*-*-*-*-*-*-*\n")
    log.prt(" ******* End of job - Total time = {:8.2f} min *****"
                 .format((end_all-start_all)/60))
    log.prt("")
    log.prt(datetime.now())


    # Close log file
    log.close()

    # tar gzip outputs, delete originals if requested
    nw = datetime.now()
    outprefix = Path(cf.res_dir).parts[-1]
    filename  = outprefix + "_" + nw.strftime("%Y%m%d_%H%M%S") \
                                +".tar.gz"
    import tarfile
    tar = tarfile.open(Path(cf.res_dir,filename), "w:gz")
    tar.add(sim_filename,arcname=os.path.basename(sim_filename))
    tar.add(log_filename,arcname=os.path.basename(log_filename))
    tar.add(cf.filename,arcname=os.path.basename(cf.filename))
    if (cf.remove_tarred):
        os.remove(sim_filename)
        os.remove(cf.filename)
        os.remove(log_filename)

    tar.close()
    print("... completed")

###############################################################################
if __name__ == "__main__":
    main(sys.argv[1:])