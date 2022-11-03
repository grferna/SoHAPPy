"""
Create a source list to be simualted and analysed from uwing parameters given 
in a configuration file and the command line.

Notes for experts:
* Change `warnings.filterwarnings('ignore')` into
`warnings.filterwarnings('error')` to have the code stopped in case of warning, and be able to identify its origin.
* The 'ignore' option is motivated by warnings issued by astropy for deprecation or too distant dates with respect to the running date.
* IERS data are not refreshed as it can take long in case of bad Internet 
or no connections at all. To refresh these data use:

..  code-block::

    # For refreshing
    print(" Refreshing IERS")
    from astroplan import download_IERS_A
    download_IERS_A
    print(" ->Done")

"""

import warnings
# warnings.filterwarnings('ignore')
# warnings.filterwarnings('error')

import sys

import time
from   datetime import datetime
from   pathlib  import Path

from configuration  import Configuration
from niceprint      import Log

# from grb            import get_from_file
from grb import GammaRayBurst
from timeslot       import Slot
from mcsim  import mc_welcome, MonteCarlo
from analyze import Analysis

# Do not refresh IERS data
from astropy.utils import iers
iers.conf.auto_download = False

###############################################################################
def welcome(log):
    """
    Good luck!

    Parameters
    ----------
    log : Log object
        See :class:`Log` for details.

    """
    import gammapy
    from __init__ import __version__

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
def main(argv):
    """
    The SoHAPPy main function.
    
    1. Manage input/output
        - Source data identifier list
        - open output simulation and log files

    2. Loop over input identifier list
        - get source data from the identifier
        - create original time slot from the source data
        - update visibilities in N and S if requested
        - save source if requested
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
    argv : List
        Command line argument list.

    Returns
    -------
    None.

    """

    # Change gammapy logging to avoid warning messages 
    import logging
    logging.basicConfig()
    log = logging.getLogger("gammapy.irf")
    log.setLevel(logging.ERROR)   
    
    ### ------------------------------------------------
    ### Configuration and output files
    ### ------------------------------------------------
    # Build the Configuration, from the defaulys, a configuratin file and
    # the command line if any.
    cf = Configuration.build(sys.argv[1:])
       
    res_dir  = cf.create_output_folder(log) # Create output folder
    data_dir = Path(cf.infolder,cf.data_dir) # Input data
    
    # This is required to have the EBL models read from gammapy
    import os
    os.environ['GAMMAPY_DATA'] = str(Path(cf.infolder,cf.extra_dir))

    # backup the configuration file for further use
    cf.write(filename = Path(res_dir,"config.yaml") )
    
    # Output file names
    sim_filename = Path(res_dir, cf.datafile) # population file
    log_filename = Path(res_dir, cf.logfile)  # log file
    
    # Open log file
    log = Log(name = log_filename, talk=not cf.silent)    
    
    # Print welcome message and configuration summary
    welcome(log)
    cf.print(log)
    
    # Check if something can be analysed
    if cf.nsrc <= 0: sys.exit(" NO ANALYSIS REQUIRED (nsrc <= 0)")

    # Prepare expert output file for individual slices
    if cf.write_slices: dump_dir = res_dir
    else: dump_dir = None
    
    ### ------------------------------------------------
    ### Identifiers of the sources to be simulated / analysed
    ### ------------------------------------------------
    srclist = cf.source_ids()

    ### ------------------------------------------------
    ### Check trigger time modification (either fixed or variable)
    ### ------------------------------------------------    
    from trigger_dates import get_trigger_dates
    dt, dt_abs = get_trigger_dates(cf.trigger)

    if dt_abs: # In case more than one value, check lengths
        if len(dt) < len(srclist):
            sys.exit(" {:s} length lower than the number of sources"
                     .format(cf.trigger))

    ### ------------------------------------------------
    ### Decode visibility info
    ### ------------------------------------------------   
    visinfo = cf.decode_keyword()

    ### ------------------------------------------------
    ### Start processing
    ### ------------------------------------------------ 
    start_pop = time.time()   # Start chronometer

    with open(sim_filename, 'w') as pop:

        #################################
        # Loop over source population   #
        #################################
        mc_welcome(cf.arrays,log=log) # Say hello, remind simulation parameters
        
        first = True # Actions for first GRB only
        # for i, item in enumerate(srclist):
        for item in srclist:

            ### Get GRB
            if isinstance(item, int):            
                fname = "Event"+str(item)+".fits.gz"
                grb = GammaRayBurst.from_fits(Path(data_dir,fname),
                                              prompt  = cf.prompt_dir, 
                                              ebl     = cf.EBLmodel,
                                              n_night = cf.n_night,
                                              Emax    = cf.Emax,
                                              dt = dt[fname] if dt_abs else dt,
                                              dt_abs  = dt_abs,
                                              magnify = cf.magnify)
                # if cfg.test_prompt: 
                #     return get_time_resolved_prompt_fromfile()

                
            elif isinstance(item, str): # this is a GRB name string
                fname    = "lightcurves/historical/GRB_"+item+".yml"
                filename = Path(cf.infolder,fname)
                grb = GammaRayBurst.historical_from_yaml(filename, 
                                                         ebl = cf.EBLmodel)

            # Assign visibilities
            for loc in ["North","South"]:
                grb.set_visibility(loc,info=visinfo)
            
            # Printout grb, visibility windows, display plots
            if (cf.niter<=1 and cf.do_fluctuate==True) \
                or cf.dbg>0 or cf.nsrc==1 :
                log.prt(grb)
                grb.vis["North"].print(log=log)
                grb.vis["South"].print(log=log)

            if cf.save_fig and cf.show > 0: # Init. pdf output
                from matplotlib.backends.backend_pdf import PdfPages
                pdf_out = PdfPages(Path(grb.id+"_booklet.pdf"))
            else: pdf_out = None
            
            if cf.show > 0 : grb.plot(pdf_out)                
            if cf.save_grb : grb.write_to_bin(res_dir)

            ###--------------------------------------------###
            #  Loop over locations
            ###--------------------------------------------###
            delay = cf.get_delay()
            
            # Create original slot (slices) and fix observation points
            origin = Slot(grb,
                          opt   = cf.obs_point,
                          name  = grb.id,
                          debug = bool(cf.dbg>1))
            
            for loc in ["North","South","Both"]:
                
                name = grb.id + "-" + loc
                log.banner(" SIMULATION  : {:<50s} ".format(name))
               
                # Create a MC object
                # It has dummy values that will be dumpped to the output
                # even if the simulation is not possible (not visible)
                mc = MonteCarlo(niter     = cf.niter,
                                fluctuate = cf.do_fluctuate,
                                nosignal  = (cf.magnify==0),
                                seed      = cf.seed,
                                debug     = cf.dbg,
                                name      = name)
                
                still_vis = False # Assumed not visible
                
                ### ------------
                ### Both sites - create a slot
                ### ------------
                if loc=="Both":
                    if grb.vis["North"].vis_night \
                       and grb.vis["South"].vis_night:
                       slot = origin.both_sites(delay = delay, 
                                                debug = (cf.dbg>1))
                       if slot != None: still_vis = True

                ### ------------
                ### North or South, create a slot
                ### ------------
                else:   
                    if grb.vis[loc].vis_night: # Apply delays to original slot
                       
                        slot = origin.copy(name="loc")    
                        still_vis = slot.apply_visibility(delay = delay[loc],
                                                          site  = loc)
                ### ------------
                ### Run simulation if still visible;, preapre analysis
                ### ------------            
                
                if still_vis: 
                    # Add IRF feature and run - Note that this can
                    # modify the number of slices (merging)
                    slot.dress(irf_dir = Path(cf.infolder,cf.irf_dir),
                               arrays  = cf.arrays,
                               zenith  = cf.fixed_zenith)
                    
                    ana = Analysis(slot, nstat = mc.niter, name = mc.name,
                                         alpha = cf.alpha, cl = cf.det_level)  
                    
                    if cf.dbg > 2: print(slot)
                           
                    mc.run(slot, ana, 
                                 boost     = cf.do_accelerate,
                                 dump_dir  = dump_dir)
                else:
                    # Define a default analysis for dump_to_file
                    ana = Analysis(origin, nstat = mc.niter, 
                                           name  = mc.name, 
                                           loc  = loc)  
                    
                # If requested save simulation to disk
                if (cf.save_simu): mc.write(Path(res_dir,name + "_sim.bin"))
                   
                # Display status - even if simulation failed (not visible)
                if cf.dbg : mc.status(log=log)
                
                ### ------------
                ### Analyze simulated data 
                ### ------------               
                if ana.err == mc.niter:  # Simulation is a success
                    ana.run()
                    if cf.dbg  : ana.print(log = log)
                    if cf.show : ana.show(pdf = pdf_out)
               
                # # Even if not detected nor visibile, dump to file
                first = ana.dump_to_file(grb, pop, header=first)
               
            if cf.save_fig and cf.show>0: pdf_out.close()
                
            # End of loop over sites
        # END of Loop over GRB

    # Stop chronometer
    end_pop = time.time()
    elapsed = end_pop-start_pop

    log.prt("\n-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*")
    log.prt(" Duration   = {:8.2f} (s)".format(elapsed))
    log.prt("  per GRB   = {:8.2f} (s)".format( (elapsed)/cf.nsrc))
    log.prt("  per trial = {:8.3f} (s)".format( (elapsed)/cf.nsrc/cf.niter))
    log.prt("-*-*-*-*-*-*-*-*- End of population simulation -*-*-*-*-*-*-*-*-*\n")
    log.prt(" ******* End of job - Total time = {:8.2f} min *****"
                 .format((end_pop-start_pop)/60))
    log.prt("")
    log.prt(datetime.now())

    # Close log file
    log.close()
    
    # tar gzip outputs, delete originals if requested
    nw = datetime.now()
    outprefix = Path(res_dir).parts[-1]
    filename  = outprefix + "_" + nw.strftime("%Y%m%d_%H%M%S") \
                                +".tar.gz"
                         
    import tarfile
    tar = tarfile.open(Path(res_dir,filename), "w:gz")
    tar.add(sim_filename,arcname=os.path.basename(sim_filename))
    tar.add(log_filename,arcname=os.path.basename(log_filename))
    tar.add(cf.filename,arcname=os.path.basename(cf.filename))
    
    if (cf.remove_tar):
        os.remove(sim_filename)
    
        os.remove(Path(res_dir,cf.filename.name)) # Remove the copy, not the original !
        
        # After CTRL-C in Spyder, or when the code crashes, the log file 
        # cannot be removed (although it was possible to overwrite it)
        # It seems to be Windows specific
        if not log.log_file.closed: log.log_file.close()
        try:                                                                                                                                                  
            os.remove(log_filename)
        except IOError:
            print("{} removal failed: locked".format(log_filename))       
       
    tar.close()
    print("... completed")

###############################################################################
if __name__ == "__main__":
    main(sys.argv[1:])