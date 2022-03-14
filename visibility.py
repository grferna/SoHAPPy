# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 13:17:27 2020

This module is organised around the :class:`visibility` class.
It combines the rise, set and night (twilight) windows, and apply the moon veto
window to the GRB data window (defined by the two extreme GRB time of the
data points) to produce the visibility windows for a given GRB on a given site.
It can also be used to check that the ones given by default are in agreement
for the default horizon value (10 degrees) and for the nights found within
24 hours.

@author: Stolar
"""
import math
from pathlib import Path

import astropy.units as u
from   astropy.time import Time
from   astropy.coordinates import AltAz, get_moon
from   astropy.table         import Table
from   astropy.coordinates   import EarthLocation, Angle

from   astroplan import Observer, FixedTarget, moon_illumination

import warnings

### Site poisitions
site_xyz = { 
    "CTA":
         { "North": EarthLocation.from_geocentric( float(5327448.9957829),
                                                   float(-1718665.73869569),
                                                   float(3051566.90295403),
                                                   unit="m"),
           "South": EarthLocation.from_geocentric( float(1946404.34103884),
                                                   float(-5467644.29079852),
                                                   float(-2642728.20144425),
                                                   unit="m")
           # Requires to have an internet connection
           # Get all possible sites with : EarthLocation.get_site_names()
           # "North": EarthLocation.of_site('Roque de los Muchachos'),
           # "South": EarthLocation.of_site('Paranal Observatory')
           # Values taken from Maria Grazia Bernardini (July 28, 2020)
           # "North": EarthLocation.from_geocentric( 5327285.09211954,
           #                                        -1718777.11250295,
           #                                         3051786.7327476,
           #                                         unit="m"),
           # "South": EarthLocation.from_geocentric(1946635.7979987,
           #                                       -5467633.94561753,
           #                                       -2642498.5212285,
           #                                        unit="m")   
           # Alternative :
           # "North": EarthLocation.from_geodetic('342.1184',
           #                                       '28.7606',2326.* u.meter)
           # "South": EarthLocation.from_geodetic('289.5972',
           #                                      '-24.6253',2635.* u.meter)
         },
         
  # from default values in
  # https://www.mpi-hd.mpg.de/hfm/HESS/pages/home/visibility/
  # Warning : use CTA-North for virtual HESS North
  "HESS":
        { "North": EarthLocation.from_geocentric( float(5327448.9957829),
                                                   float(-1718665.73869569),
                                                   float(3051566.90295403),
                                                   unit="m"),
          "South": EarthLocation.from_geodetic(lat=Angle('-23d16m18.0s'),
                                      lon=Angle('16d30m0.0s'),
                                      height=1800*u.m)
        }
 }

__all__ = ["Visibility"]
###------------------------------------------------------------------------
def Df(x):
    """
    Returns a time in Julian day format if the argument is finite
    """
    if math.isfinite(x):
        return Time(x,format="jd")
    else:
        return x
###------------------------------------------------------------------------
def Dp(x):
    """
    Returns a time in ISO format if the argument is an astropy 
    :class:`Time`, and if not returns the argument (unchanged).
    """
    if isinstance(x,Time):
        return x.iso
    else:
        return x

###############################################################################
class Visibility():
    """
    This class defines the visibility periods for a given GRB and a certain
    site (North or South).
    It can be called to update the default visibilities given with the GRB data
    file, in particular to modify the minimum altitude for a source to be
    decently detectable.
    The method, :class:`check` is used to compare the visibility
    windows with the one given by default in the GRB file or any other
    pre-loaded visibility.

    Excerpt from the astroplan documentation:
        
    * Moonrise is defined as the instant when, in the eastern sky, under ideal meteorological conditions, with standard refraction of the Moon's rays, the upper edge of the Moon's disk is coincident with an ideal horizon.

    * Moonset is defined as the instant when, in the western sky, under ideal meteorological conditions, with standard refraction of the Moon's rays, the upper edge of the Moon's disk is coincident with an ideal horizon.

    The Moon angular diameter varies between 29.3 to 34.1 arcminutes 
    (Wikipedia), namely 0.488 and 0.568 degree. The rise time is when the moon is below the horizon at a negative angle half of these values, respectively -0.244 and -0.284 degree
    
    """

    ###------------------------------------------------------------------------
    def __init__(self,grb,loc,depth=0, observatory="CTA"):
        """
        Visibility constructor, setting a full visibility of the GRB, from the
        start to the stop of the GRB data. 
        The members follow the elements of the original default visibility 
        files. 

        Parameters
        ----------
        grb : GammaRayBurst instance
            The objetc to which the visibility will be attached
        loc : String
            Site (North or Souht)
        observatory: String
            The simulated observatory. default is "CTA".
        Returns
        -------
        None.

        """
        
        self.status  = "init"
        self.site    = site_xyz[observatory][loc]
        self.target  = FixedTarget(coord=grb.radec, name=grb.name)
        self.tstart  = grb.t_trig
        self.tstop   = grb.t_trig + min(grb.tval[-1],depth*u.day)
        self.name    = grb.name+"_"+loc

        self.altmin  = 0*u.deg # GRB Minimal allowed altitude

        # These three variables were defined by M.G.Bernardini in the first 
        # version of the visibilty, without moon veto, and with a visibility 
        # computed for the first night only. They are kept for consistency but 
        # have a somewhat smaller importance with the presence of moon vetoes 
        # and a visibility that can be computed on more than one night.
        # However the vis_prompt varaibale still indicate the chance to have
        # the prompt emission detected if the alert and slewing times are not
        # too long.
        # Here below, better definitions of these variables are given.
        
        # Originally: Visible any moment of the year from the site
        # This means that the GRB appears above the defined horizon whathever
        # the other conditions are. In particular, mitigation against the 
        # Moonlight would make it visible from the first or next nights.
        self.vis         = True
        
        # Originally: Visible any moment within the 24h after the trigger from 
        # the site, names vis_tonight in the GRB file.
        # Changed to vis_night and True if the GRB is visible during any night
        # This the variable on which the decision of simulation is given.
        self.vis_night = True
        
        # Originally: Visible at the moment of the GRB trigger
        # Keeps the original meaning but add the moon veto, which can differ
        # with the assumprions made with the affordable Moonlight.
        self.vis_prompt  = True

        # Visible above min. alt. - list of pair
        self.t_true     = [[self.tstart, self.tstop]]

        # Astronomical twilight - list of pair
        self.t_twilight = [[self.tstart, self.tstop]]

        # Rise and set of the target - list of pair
        self.t_event    = [[self.tstart,self.tstop]]  

        # Nights
        # self.t_night  = [[]] # Never used - to be deleted

        # Moon period veto - Default is no veto
        self.moon_maxalt     = 90*u.deg # Maximal allowed altitude
        self.moon_mindist    =  0*u.deg # Minimum distance to source
        self.moon_maxlight   =  1       # Maximum allowed brightness

        self.t_moon_up       = [[]] # Altitude exceeds moon_maxalt
        self.moon_too_bright = [] # Moon brigthness above threshold
        self.moon_too_close  = [] # Moon distance too small

        return
    
    ###-----------------------------------------------------------------------
    @classmethod
    def from_fits(cls, grb, hdr, hdul, hdu=1, loc="None"):
        """
        Default visibility from input file.
        
        * The start and stop dates are searched during 24h after the trigger and correspond to the first visibility interval.
        
        * Does not report a second visibility interval during 24h, that should be possible only if the target is promptly visible (about 15% of the targets)
        
        Parameters
        ----------
        grb : TYPE
            DESCRIPTION.
        hdr : TYPE
            DESCRIPTION.
        hdul : TYPE
            DESCRIPTION.
        hdu : TYPE, optional
            DESCRIPTION. The default is 1.
        loc : TYPE, optional
            DESCRIPTION. The default is "None".

        Returns
        -------
        None.

        """
        cls = Visibility(grb,loc)  # This calls the constructor

        vis = Table.read(hdul,hdu=hdu)

        def f(t,loc):
            t = Time(t.data,format="jd",scale="utc")
            if (loc == "North"): return [ [ t[0:2][0], t[0:2][1] ] ]
            if (loc == "South"): return [ [ t[2:4][0], t[2:4][1] ] ]

         # Visibility has been computed with this minimum altitude
        if (loc == "North"):
            cls.vis          = hdr['V_N_ANYT']
            cls.vis_night    = hdr['V_N_TNG'] # formerly vis_tonight
            cls.vis_prompt   = hdr['V_N_PR']

        if (loc == "South"):
            cls.vis          = hdr['V_S_ANYT']
            cls.vis_night    = hdr['V_S_TNG'] # formerly vis_tonight
            cls.vis_prompt   = hdr['V_S_PR']

        cls.altmin     = vis.meta["MIN_ALT"]*u.deg # Minimum altitude
        cls.t_true     = f(vis["True"],loc)
        cls.t_twilight = f(vis["Twilight"],loc)
        cls.t_event    = f(vis["Event"],loc)

        #print(self.grb.name," : visibility read for ",loc)

        return cls

    ###-----------------------------------------------------------------------
    @classmethod
    def compute(cls,grb, loc, 
                    param       = None,
                    npt         = 150,
                    force_vis   = False,
                    debug       = True):
        """
        
    Compute the visibility periods for a given GRB and site. This constructor 
    takes as arguments a grb (:class:'GammaRayBurst`) and a location (string), 
    and all the parameters required for the computation.
    
    Note that all time variables are expressed in Julian days (to use `sort`) 
    and are then copied as :class:`Time` objects later into the class variables.
    
    The algorithm is the following:
    
        1. Build periods for:
            * Nights (*t_night*), and check if trigger occurs during night 
            (*is_night*);
            
            * Potential moon vetoes (*t_moon_alt_veto*) due to the Moon above 
            the defined horizon (*altmoon*);
            
            * Check (*True*, *False*) whether these Moon veto periods are kept 
            by the moon brightness and distance to the source 
            (*moonlight_veto*). If this is the case, keep the corresponding 
            moon veto period in *t_moon_veto* otherwise discard the period. 
            In order to have all Moon periods kept (i.e. veto is valid as soon 
            as Moon is above *altmoon*), *moondist* should be maximised 
            (veto at any distance) and *moonlight* should be minimised 
            (even if no moonligt, veto is valid);
            
            * Above horizon (*t_above*) and whether the object is above the 
            horizon (*altmin*) at trigger time.
    
        2. Put all *start* and *stop* of all these periods in a list, 
        sort the list, resulting in a series of ordered “ticks”.
        3. For each consecutive tick pairs in the list:
            * Compute the mean time (middle of the a tick pair)
            * Check if that time belongs to one of the *night*, *above*, or 
            *bright* (i.e. in the available data interval) intervals and not 
            to any  *moon* interval. If so get True, otherwise False.
    
        4. For each of the tick pairs compute the Boolean 
        `visible = bright and dark and above and moon` and get the visibility 
        windows when True.

        Parameters
        ----------
        cls : Visibility Object
            The present instance.
        grb : TYPE
            DESCRIPTION.
        loc : String
            Characterize the site, typically "North" or "South.
        param : Dictionnary, optional
            A dictionnary of parameters to compute the visibility. 
            The default is None.
        npt : integer, optional
            Number of grid points for horizon crossing. The default is 150.
        force_vis : Boolean, optional
            If True the visibility is unlimited. The default is False.
        debug : bool, optional
            Print additional comments at excecution time if True .The default is False.

        Returns
        -------
        Visibility Object
            The updated instance.

        """

        # Decode the parameter dictionnay or set defaults
        if param != None:
            observatory = param["where"]
            altmin      = u.Quantity(param["altmin"])
            altmoon     = u.Quantity(param["altmoon"])
            moondist    = u.Quantity(param["moondist"])
            moonlight   = param["moonlight"]
            depth       = param["depth"]
            skip        = param["skip"]        
        else:
            observatory = "CTA"
            altmin      = 10*u.degree
            altmoon     = 0*u.degree
            moondist    = 0*u.degree
            moonlight   = 1
            depth       = 3
            skip        = 0

        cls = Visibility(grb,loc,depth=depth, observatory=observatory)  # This calls the constructor
                
        ###---------------------------------------------------
        def valid(t0,tslices):
            if len(tslices[0]) == 0 : return False # No slice !
            ok = False
            for slices in tslices:
                if (t0 >= slices[0] and t0 <= slices[1]):
                    if (ok == False): ok = True
            return ok
        ###---------------------------------------------------

        cls.altmin        = altmin
        cls.moon_maxalt   = altmoon
        cls.moon_mindist  = moondist
        cls.moon_maxlight = moonlight

        cls.status    = "Updated"

        obs  = Observer(location  = cls.site,
                        name      = cls.name,
                        timezone  ="utc")

        ###---------------------
        ### Find the nights  ---
        ###---------------------
        if force_vis: 
            # If the visibility is forced, a single night covers all the data
            t_night = [[cls.tstart.jd, cls.tstop.jd]]
            is_night = True
        else: is_night, t_night  = cls.nights(obs, skip=skip, npt=npt)

        ###---------------------
        ### MOON VETOES (high enough, close enough, bright enough) ---
        ###---------------------
        if force_vis:
            # If the visibility is forced, the Moon period list is empty
            t_moon_alt_veto = [[]]
            t_moon_veto = [[]]
        else:
            # These are the perioss when the Moon is above horizon
            t_moon_alt_veto    = cls.moon_alt_veto(obs, npt=npt)
            # When Moon is up, check if moonlight is affordable
            t_moon_veto = []
            for dt in t_moon_alt_veto:
                (too_bright, too_close) = cls.moonlight_veto(dt)
                cls.moon_too_bright.append(too_bright)
                cls.moon_too_close.append(too_close)
                # If the Moon being above the horizon itgives too much
                # light, add the corresponding perido to the Moon veto
                if too_bright or too_close: t_moon_veto.append(dt)
            # In case there is no Moon veto period, then conclude with
            # an empty array of [t1,t2] arrays
            if len(t_moon_veto) == 0: t_moon_veto = [[]]

        ###---------------------
        ### HORIZON ---
        ###---------------------
        (high, t_above) = cls.horizon(obs)
        
        ###---------------------
        ### Collect the ticks from all periods (authorised and forbidden)
        ###---------------------
        
        # First tick is the start of data
        ticks = [cls.tstart.jd]

        # Restrict the windows to the last night end or the GRB data length
        if cls.tstop < Df(t_night[-1][1]):
            # The GRB data stop before the end of last night
            # print(" >>>> Analysis shortened by lack of data")
            ticks.extend([cls.tstop.jd])
        else:
            # Set the end at last night for convenience
            cls.tstop = Df(t_night[-1][1])

        # Add the ticks of all previously computed wnidows
        for elt in t_night       : ticks.extend(elt)
        for elt in t_above       : ticks.extend(elt)
        for elt in t_moon_veto   : ticks.extend(elt)

        # Sort in time
        ticks.sort() # Requires numerical values -> all times are in jd

        if (debug):
            print("Ticks : ",len(ticks))
            for t in ticks:
                print("{:10s} {:<23s} ".format(cls.name, Df(t).iso))
                
        ###---------------------
        ### Check the visibility within all tick intervals
        ###---------------------
        # Loop over slices and check visibility
        if (debug): # Header
            print(" {:<23s}   {:<23s} {:>10s} {:>6s} {:>6s} {:>6s} {:>6s}"
                  .format("T1", "T2", "bright", "dark", "above", "moon.","vis."))

        t_vis   = []
        for i in range(len(ticks)-1):
            t1 = ticks[i]
            t2 = ticks[i+1]
            tmid = 0.5*(t1+t2)
            # Check if the current tick interval corresponds to an 
            # authorised or forbidden window
            
            # The GRB shines (in the limit of the available data
            bright   = valid(tmid,[[cls.tstart.jd,cls.tstop.jd]])
            
            # It is night
            dark     = valid(tmid,t_night)
            
            # It is above the horizon 
            above    = valid(tmid,t_above)
            
            # The moon authorises the observation
            not_moon = not valid(tmid,t_moon_veto) # Moon acts as a veto
            
            # In the end the GRB is visible if all conditions are fulfilled
            visible = bright and dark and above and not_moon
            if (visible): t_vis.append([t1, t2])

            if (debug):
                if math.isinf(t1): t1 = "--"
                else : t1 = Df(t1).iso

                if math.isinf(t2): t2 = "--"
                else: t2 = Df(t2).iso
                print(" {:>23}   {:>23} {:>10} {:>6} {:>6} {:>6} {:>6}"
                      .format(t1, t2,
                              bright, dark, above, not not_moon, visible),
                      end="")
                if (visible): print(" *")
                else: print()
                
        ###---------------------------------------        
        ### Write back all intervals into Time and into Class
        ###---------------------------------------        
        if len(t_night[0])==0 : # Night periods
            cls.t_twilight  = [[]]
        else:
            cls.t_twilight  = []
            for elt in t_night:
                cls.t_twilight.append( [Df(elt[0]), Df(elt[1])] )

        if len(t_above[0])==0 : # Above horizon period
            cls.t_event  = [[]]
        else:
            cls.t_event  = []
            for elt in t_above:
                cls.t_event.append( [Df(elt[0]), Df(elt[1])] )

        if len(t_moon_alt_veto[0])==0 : # Moon veto periods
            cls.t_moon_up  = [[]]
        else:
            cls.t_moon_up  = []
            for elt in t_moon_alt_veto:
                cls.t_moon_up.append( [Df(elt[0]), Df(elt[1])] )
                
        ###---------------------------------------        
        ### Finalise the visibility windows and flags
        ###---------------------------------------         
           
        cls.vis = False
        cls.vis_night = False
        cls.vis_prompt  = False
        
        # At least a period above the horizon
        # Note that this function could stop as soon as no window above
        # the horizon is found, which is not the case in this implementation 
        if len(t_above) > 0: cls.vis = True        
        
        # At least a visibility period for observation
        if len(t_vis) > 0: 
            cls.vis_night = True
            
            # In this first window the prompt is visible    
            if  valid(grb.t_trig.jd,[t_vis[0]]):
                cls.vis_prompt=True
            
            # Store definitively the visibility windows
            cls.t_true = [] # Warning: default is the GRB window
            for elt in t_vis:
                cls.t_true.append( [Df(elt[0]), Df(elt[1])] )             
                            
        # There is no visibility window at all - sad World             
        else:
            cls.t_true  = [[]]
           
        return cls

    ###-----------------------------------------------------------------------
    @classmethod
    def read(cls,name,folder=".",debug=False):
        """
        Read a visibility instance from disk


        Parameters
        ----------
        cls : TYPE
            DESCRIPTION.
        name : TYPE
            DESCRIPTION.
        folder : TYPE, optional
            DESCRIPTION. The default is ".".
        debug : TYPE, optional
            DESCRIPTION. The default is False.

        Returns
        -------
        vis : TYPE
            DESCRIPTION.

        """

        import pickle
        import os, sys        
        filename = Path(folder,name)
        if os.path.isfile(filename):
            infile  = open(filename,"rb")
            cls =  pickle.load(infile)
            infile.close()
            if (debug): print(" <<<< Visibility read from : ",filename)
        else:
            sys.exit(" Visibility file "+filename.name+" does not exist !")

        return cls

    ###-----------------------------------------------------------------------
    def write(self, folder=".",debug=False):
        """
        Write current visibility instance to disk

        Parameters
        ----------
        folder : TYPE, optional
            DESCRIPTION. The default is ".".
        debug : TYPE, optional
            DESCRIPTION. The default is False.

        Returns
        -------
        None.

        """

        import pickle
        from pathlib import Path

        filename = Path(folder,self.name+"_vis.bin")
        outfile  = open(filename,"wb")
        pickle.dump(self,outfile)
        outfile.close()
        if (debug): print(" >>> Visibility written to : ",filename)

        return

    ###-----------------------------------------------------------------------
    def nights(self,obs, skip=0, npt=150):
        """


        Parameters
        ----------
        obs : TYPE
            DESCRIPTION.
        is_night : TYPE
            DESCRIPTION.
        skip : TYPE, optional
            DESCRIPTION. The default is 0.
        tstop : TYPE, optional
            DESCRIPTION. The default is None.

        Returns
        -------
        tnights : TYPE
            DESCRIPTION.

        """

        tnights = []
        inight  = 0 # night (after trigger) counter

        # Get the first night : can be the current night
        is_night = obs.is_night(self.tstart, horizon = -18*u.deg)

        if (is_night):
            search="previous"
        else:
            search = "next"

        t_dusk = obs.twilight_evening_astronomical(self.tstart,
                                                    which = search,
                                                    n_grid_points = npt)
        t_dawn = obs.twilight_morning_astronomical(t_dusk,
                                                    which="next",
                                                    n_grid_points = npt)
        # Omit first night if requested
        inight = 1 # night counter
        if (skip ==0):
            tnights.append([t_dusk.jd, t_dawn.jd])

        # Add subsequent nights until reaching the end of GRB data
        while (t_dusk < self.tstop): # and (inight < self.depth):
            t_dusk = obs.twilight_evening_astronomical(t_dawn,
                                                        which = "next",
                                                        n_grid_points = npt)
            t_dawn = obs.twilight_morning_astronomical(t_dusk,
                                                        which = "next",
                                                        n_grid_points = npt)
            if (inight >= skip):
                tnights.append([t_dusk.jd, t_dawn.jd])
            
            inight +=1

        # For test, add the previous night
        # t_dawn0 = obs.twilight_morning_astronomical(self.grb.t_trig,
        #                                            which="previous",
        #                                            n_grid_points = npt)
        # t_dusk0 = obs.twilight_evening_astronomical(t_dawn0,
        #                                             which="previous",
        #                                             n_grid_points = npt)
        # tnights.append([t_dusk0.jd, t_dawn0.jd])
        if len(tnights) ==0:
            import sys
            sys.exit("No night found, please check your input parameters")

        return (is_night, tnights)

    ###-----------------------------------------------------------------------
    def horizon(self, obs, npt=150):
        """


        Parameters
        ----------
        obs : TYPE
            DESCRIPTION.
        npt : TYPE, optional
            DESCRIPTION. The default is 150.

        Returns
        -------
        high : TYPE
            DESCRIPTION.
        TYPE
            DESCRIPTION.

        """

        t_above = []

        # Get first period above horizon : can be the present period...
        high = obs.target_is_up(self.tstart, self.target,
                                horizon = self.altmin)

        if (high): search="previous"
        else: search = "next"

        t_rise = obs.target_rise_time(self.tstart,
                                      self.target,
                                      which   = search,
                                      horizon = self.altmin,
                                      n_grid_points = npt)

        # If rise time is undefined, this means that the GRB is always above
        # or below the horizon - Otherwise the set time can be found.
        if (math.isnan(t_rise.jd)):
            if (high):
                self.vis = True
                return high, [[self.tstart.jd,self.tstop.jd]]
            else:
                self.vis = False
                return high, [[]]
        else:
            self.vis = True
            t_set = obs.target_set_time(t_rise,
                                        self.target,
                                        which="next",
                                        horizon = self.altmin,
                                        n_grid_points = npt)

            t_above.append([t_rise.jd,t_set.jd])


            # Add a subsequent above-horizon periods until GRB end of data
            while (t_set < self.tstop):
                t_rise = obs.target_rise_time(t_set,
                                          self.target,
                                          which="next",
                                          horizon = self.altmin,
                                          n_grid_points = npt)
                t_set = obs.target_set_time(t_rise,
                                            self.target,
                                            which="next",
                                            horizon = self.altmin,
                                            n_grid_points = npt)
                t_above.append([t_rise.jd,t_set.jd])

        return (high, t_above)
    ###-----------------------------------------------------------------------
    def moonlight_veto(self,dt,debug=False):
        """
        Check if the Moon period defined by the rise and set time correspond
        to a situation where the moon is too bright or too close from the
        source.
        If this is the case (too bright or too close), returns True
        (the veto is confirmed).

        """
        too_bright = False
        too_close  = False

        # Check moon illumination
        for t in dt:
            moonlight = moon_illumination(Df(t))
            if (moonlight >= self.moon_maxlight):
                too_bright = True
                if (debug):
                    print("Moonlight :",moonlight," too bright ! -> confirmed")
                break

        # Check distance to source at rise and set
        for t in dt:
            moon_radec = get_moon(Df(t), self.site)
            dist = moon_radec.separation(self.target.coord)
            if dist <= self.moon_mindist:
                too_close = True
                if (debug): print(" Moon Distance : ",dist,"too close !")
                break

        return (too_bright, too_close)

    ###----------------------------------------------------------------------------
    def moon_halo(x, r0 = 0.5, rc=30, epsilon=0.1, q0 = 1):
        """
        Returns the moon light intensity (hand-made model) as a function of distance r
        It is assumed that the intensity is constant (q0) along the moon radius r0, and reach
        the fraction epsilon at the critical distance rc, following a 1/r2 function:
        1/(a*(x-r0)**2 +c)
        """
        f = 1/ ( (1 -epsilon)/(q0*epsilon)/(rc-r0)**2 * (x-r0)**2 + 1/q0)
        #f = 0.5*(1 - abs(r0-x)/(r0-x))* f + 0.5*(1 - abs(x-r0)/(x-r0))*q0
        return f

    ###----------------------------------------------------------------------------
    def moon_halo_veto(q0, threshold=0.1, r0 = 0.5, rc=30, epsilon=0.1):
        """
        Returns the distance at which the moon intensity reaches the threshold
        This is the analytical inverse of the moon_halo function
        """
        a = (1 -epsilon)/epsilon/q0/(rc-r0)**2
        return math.sqrt((1/threshold - 1/q0)/a)

    ###-----------------------------------------------------------------------
    def moon_alt_veto(self, obs, npt=150):
        """
        The first veto is the moon alitude.
        First find windows where the Moon is too high

        Parameters
        ----------
        obs : TYPE
            DESCRIPTION.
        twindow : TYPE
            DESCRIPTION.
        altmin : TYPE, optional
            DESCRIPTION. The default is 10*u.deg.
        npt : TYPE, optional
            DESCRIPTION. The default is 150.

        Returns
        -------
        tmoons : TYPE
            DESCRIPTION.

        """

        tmoons = []

        # Is the Moon there at trigger tigger time ?
        radec = get_moon(self.tstart,obs.location)
        altaz = radec.transform_to(AltAz(location=obs.location,
                                         obstime=self.tstart))

        # Search next rise except if Moon is already here
        search="next"
        if  (altaz.alt > self.moon_maxalt): search="previous"

        t_rise = obs.moon_rise_time(self.tstart,
                                    which = search, horizon=self.moon_maxalt,
                                    n_grid_points = npt)
        if (math.isnan(t_rise.jd)):
            # Moon will never rise
            print(" >>>>> Moon will never rise above ",self.moon_maxalt)
            return [[]] # No veto period

        t_set  = obs.moon_set_time(t_rise,
                                   which="next", horizon=self.moon_maxalt,
                                   n_grid_points = npt)

        tmoons.append([t_rise.jd, t_set.jd])

        # Add subsequent nights until reaching the end of GRB data
        while (t_set.jd < self.tstop.jd):
            t_rise = obs.moon_rise_time(t_set,
                                        which = "next", horizon=self.moon_maxalt,
                                        n_grid_points = npt)
            t_set  = obs.moon_set_time(t_rise,
                                       which = "next",  horizon=self.moon_maxalt,
                                       n_grid_points = npt)

            tmoons.append([t_rise.jd, t_set.jd])

        if len(tmoons): return tmoons
        else: return [[]]

        return tmoons

    ###------------------------------------------------------------------------
    def print(self,log=None, alt=None):
        """
        Print out the GRB night, above-the-horizon periods, and default
        visibility window.

        Parameters
        ----------
        loc : String, optional
            Either "North" or "South". The default is None.
        log : TextIO, optional
            Log file. The default is None.
        alt : Visibility instance
            Get the values from the Visibility object (used for comparisons)

        Returns
        -------
        None.

        """
        from utilities import Log
        if log == None: log = Log()
        
        log.prt("=================   {:10s}   {:10s}   ================"
          .format(self.name,self.status))
        log.prt(' Visible : {} - tonight, prompt : {}, {})'
              .format(self.vis, self.vis_night,self.vis_prompt))
        log.prt(' Altitude : Horizon > {:3.1f} - Moon > {:4.2f}'
              .format(self.altmin, self.moon_maxalt))
        #log.prt(" Trigger: {}".format(self.t_trig.datetime))
        
        #   WARNING : might be wrong since vis_tonight is not vis_night
        if self.vis_night or self.status =="Updated": 
            log.prt("+----------------------------------------------------------------+")

            ###------------------
            def show(t,case="Dummy"):
                if len(t[0]) == 0:
                    log.prt(" {:6s} : {:26s} * {:26s}".format(case,"--","--"))
                    return
                for i, elt in enumerate(t):
                    t1 = elt[0]
                    t2 = elt[1]
                    log.prt(" {:6s} : {} * {}".format(case,
                                                      t1.datetime,
                                                      t2.datetime),end="")
                    # t1  = (t1-self.grb.t_trig).sec*u.s
                    # t2  = (t2-self.grb.t_trig).sec*u.s
                    # log.prt("        : {:7.2f} {:6.2f} * {:7.2f} {:6.2f}"
                    #       .format(t1,self.grb.altaz(loc=loc,dt=t1).alt,
                    #               t2,self.grb.altaz(loc=loc,dt=t2).alt))
                    if case=="Moon":
                        log.prt(" B:{} D:{}"
                                .format(str(self.moon_too_bright[i])[0],
                                        str(self.moon_too_close[i])[0]))
                    else:
                        log.prt("")
                return
            #-------------------

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                show(self.t_event,case="Event") # Event - above altmin
                show(self.t_twilight,case="Twil.")  # Twilight - Dark time
                show(self.t_moon_up,case="Moon")  # Moon altitude veto
                show(self.t_true,case="True")  # True : dark time + altmin + triggered
            log.prt("+----------------------------------------------------------------+")

        return
    ###------------------------------------------------------------------------
    def check(self, view, loc=None, delta_max = 5*u.s, log=None):
        """
        Checks whether the visibility found in this code is
        identical to the one in argument.
        In particular, allow checking the default visbility for altmin=10°
        and one night (The computation was done by maria Grazia Bernardini (MGB).
        See README file for more information.

        Parameters
        ----------
        vis: Visibility
            The visibility to be compared wiht
        delta_max : float, optional
            Max tolerance in seconds on window time limits.
            The default is 5..
        log : file pointer, optional
            Allows having the output both on screen and in a file. The default is None.

        """

        #----------------------------------------------------------------
        def status(tnew,torg,case=None):
            """
            This function is part of the check method only, and factorize a
            debugging printout

            Parameters
            ----------
            tnew : a time object pair in a list
                The visibility windows in this code.
            torg : a time object pair in a list
                The visibility windows in the original data.
            case : string, optional
                Some words describingthe data sets. The default is None.

            Returns
            -------
            bool
                Return True if both time set are identical within the tolerance
                delta_max.

            """
            delta1 = abs(tnew[0] -torg[0])
            delta2 = abs(tnew[1] -torg[1])
            if (delta1 > delta_max or delta2 > delta_max):

                if (log != None):
                    log.prt("   ==> {:>10s}: {} * {}"
                            .format(case,tnew[0].datetime,tnew[1].datetime))
                    log.prt("   ==> {:>10s}: {} * {}"
                          .format("was",torg[0].datetime,torg[1].datetime))
                    log.prt("   ==> {:>10s}: {:26.2f} * {:26.2f}"
                          .format("Delta",delta1.sec,delta2.sec))
                    log.prt("   ==> Not compatible with original values")

                return False
            else:
                return True
        #----------------------------------------------------------------

        matching = True
        log.prt(" *** Check {} {}, '{}' and '{}' with tolerance : {}"
                .format(self.grb.name,self.loc,self.name,view.name,delta_max),end=" ")

        # Check that general visibilities agree - if not return False
        if (self.vis != view.vis):
            log.prt(" ==> Vis wrong ", end="")
            matching = False
        if (self.vis_tonight != view.vis_tonight):
            log.prt(" ==> Vis_tonight wrong ",end="")
            matching = False
        if (self.vis_prompt != view.vis_prompt):
            log.prt(" ==> Vis_prompt wrong ",end="")
            matching = False
        if len(self.t_true) > 1:
            log.prt(" ==> >1 window",end="")
            matching = False

        if (not matching):
            print()
            return matching

        # If visibilities agree and there is nothing to compare with, return True
        if (self.vis == False):
             log.prt ("--- not visible")
             return True
        if (self.tonight == False):
             log.prt ("--- not tonight")
             return True

        # both "tonight" are OK, compare delta-time

        if (self.tonight and view.vis_tonight):
            print()
            # status(self.t_above,self.grb.t_event,case = "Above")
            # status(self.t_night,self.grb.t_twilight,case = "Night")
            matching = status(self.t_true[0],view.t_true[0],case = "Vis")
            if matching: log.prt("--- ok")
            else: log.prt("--- DOES NOT MATCH")
        return matching
    

###---------------------------------------------------------------------
if __name__ == "__main__":
    """
    Compute the visibilities for some GRB and compare to the default stored in
    the GRB class. Update the GRB visibility windows.

    * Events with Astroplan problem (risetime too close from tref)
    astroplan_north = [522, 644]
    astroplan_south = [233, 769]

    * Events for which MG misses a short window
    short_missed_North = [129, 174, 197, 214, 309, 380, 381, 479, 488, 502, 609,
                         673, 933, 965]
    short_missed_South = [24, 30, 182, 186, 319, 338, 444, 475, 734, 772, 826,
                         879, 917, 986]

    * Events with > 1 visibility window
    vis2_North = [75, 137, 139, 151, 153, 239, 270, 353, 507, 727, 859, 906,
                  923, 948]
    vis2_South = [85, 115, 414, 754, 755]

    """

    from   utilities import Log, highlight
    from   SoHAPPy import get_grb_fromfile
    from pathlib import Path
    import grb_plot as gplt
    
    # Read default configuration
    from configuration import Configuration
    cf = Configuration("config.yaml")
                
    # Put check=True to have the computed visibility compared to the defaukt 
    # original ones later
    check = False
    if check:
        cf.visibility["altmin"]    = 10*u.deg
        cf.visibility["moondist"]  = 0*u.deg
        cf.visibility["moonlight"] = 1.
        cf.visibility["depth"]     = 1*u.day
        cf.visibility["skip"]      = 0
    
    ngrb     = 1 # 250
    ifirst   = [2] # ["190829A"]

    # Superse some values if needed
    # cf.dbg       = 1
    # cf.show      = 0
    # cf.vis_cmp   = True    
    # cf.save_grb  = False # (False) GRB saved to disk -> use grb.py main
    # cf.res_dir   = "."

    log_filename    = cf.res_dir  + "/visibility.log"
    log = Log(name  = log_filename,talk=True)
    
    # Print configuration with possible superseded values
    cf.print(log)
    
    # GRB list to be analysed
    if type(ifirst)!=list: grblist = list(range(ifirst, ifirst + ngrb))
    else:  grblist = ifirst   
    
    # # Loop over GRB list
    for item in grblist:

        grb = get_grb_fromfile(item,
                               config = cf,
                               grb_folder = cf.grb_dir,
                               log = log)
        print(grb)
        gplt.spectra(grb,opt="Packed")
        for loc in ["North","South"]:
            grb.vis[loc].print()
            gplt.visibility_plot(grb, loc=loc)               

        # THi shas to be rewrittend as the visibilitysnow computed from 
        # withthe GRB class
        # Handle visibilities for both sites
        # for loc in ["North","South"]:
            
        #     if check: # Compare to default visibility
        #         log.prt("\n--------------- D E F A U L T  -----------------\n")
        #         grb.vis[loc].print(log=log)
        #         if (check and ngrb<30 and cf.show>0):
        #             gplt.visibility_plot(grb, loc=loc)
                    
        #         # Save old visibilities
        #         import copy
        #         vis_def = copy.deepcopy(grb.vis[loc])          

        #         log.prt()("\n--------------- C H E C K  ----------------\n")
        #         grb.vis[loc].check(vis_def,log=log,delta_max=1*u.s)
                
        #     else:
        #         grb.vis[loc].print()
        #         gplt.visibility_plot(grb, loc=loc)               

    log.close()

    print(" All done !")