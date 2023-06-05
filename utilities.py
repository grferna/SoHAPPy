# -*- coding: utf-8 -*-
"""
Created on Fri Jan 11 14:41:11 2019

@author: Stolar
"""
import sys

###----------------------------------------------------------------------------
def pause():
    """
    Used to pause plot display in interactive mode on a shell script. In the
    abscence of a call to that function figures wil stack on the screen during
    the run and all disappear at the end of the run.
    Using this, figures will be stacked on screen and displayed for each event
    until they are closed by the user.

    Returns
    -------
    None.

    """
    import matplotlib.pyplot as plt

    plt.show(block=True)
    return

###----------------------------------------------------------------------------
def subset_ids(nmax, nsets, debug=False):
    """
    This is a simple code defining nsets interval for a list of integer
    starting at 1 up to nmax. If nmax is not divisible by nsets, the rest 
    gives and extra set.

    Parameters
    ----------
    nmax : integer
        Maximal nubmer.
    nsets : integer
        Number of sets.
    debug : Boolean, optional
        If True, verbosy. The default is False.

    Returns
    -------
    dsets : list of List
        The list of concsecutiveintervals.

    """
    if nsets >= nmax:
        return [1,nmax]
    
    delta = int(nmax/nsets) # regular set size
    rest  = nmax%nsets # Last set size

    # Define low and high values of the intervals       
    ids_low  = [i for i in range(1,nmax,delta)]
    ids_high = [i for i in range(delta,min(nmax+delta,nmax),delta)]
    if len(ids_high) < len(ids_low):
        ids_high += [nmax]
    elif ids_high[-1]<nmax:
        ids_high[-1] = nmax
        
    if debug:
        print("steps = ",delta, " uncovered = ",rest)
        print([id for id in ids_low], " -> ",len(ids_low)," items")
        print([id for id in ids_high], " -> ",len(ids_high)," items") 
        
    # Create interval list
    dsets = [[idl, idh] for (idl, idh) in zip(ids_low, ids_high)]
    
    # Check counts
    icount=0
    for ds in dsets:
        for item in range(ds[0],ds[1]+1):
            icount+=1
    if icount != nmax: 
        print(dsets)
        sys.exit(f"Total entries = {icount:}")
    
    return dsets

###----------------------------------------------------------------------------
def file_from_tar(folder=None, tarname=None, target=None):
    """


    Parameters
    ----------
    folder : string, optional
        The folder to scan. The default is "None".
    tarname : string, optional
        The archive name in case more than one in the folder.
        The default is None.
    target : string, optional
        The file to be found in the archive, or a file name with the same
        extension. The default is None.

    Returns
    -------
    A pointer to a file in memory

    """

    import tarfile
    from pathlib import Path

    tag = "file_from_tar: "

    ### ------------------------
    ### Get archive file name
    ### ------------------------
    if not Path(folder).is_dir():
        sys.exit("{} Folder not found".format(tag))

    if target == None:
        sys.exit("{} Specify a target in the archive".format(tag))

    if tarname == None:
        # Find the archive in the folder
        p = Path(folder).glob('*.tar.gz')
        files = [x for x in p if x.is_file()]
        if len(files)>1:
            sys.exit("{} More than one .tar.gz file, specify a name"
                     .format(tag))
        else:
            tarname = files[0]
    print("{} found {}".format(tag,tarname))

    ### ------------------------
    ### Open tar file, get members, check data.txt exists
    ### ------------------------
    tar = tarfile.open(tarname, "r:gz")

    # If the target is not found explicitely, tires a file with same extension
    if not target in [member.name for member in tar.getmembers()]:

        print("{} No {} in archive. Tries with extension"
              .format(tag, target))

        # find members with correct extension
        extmatch = \
            [(m.name if Path(m.name).suffix==Path(target).suffix else None) \
             for m in tar.getmembers()]
        extmatch = list(filter(None,extmatch)) # Remove None

        if len(extmatch)>1:
            sys.exit("{} More than one file matching in archive (try largest?)"
                     .format(tag))
        elif len(extmatch)==0:
            sys.exit("{} No file matching extension in the archive"
                     .format(tag))
        else:
            print("{} {} matches {}".format(tag, extmatch[0],target))
            target = extmatch[0]

    # At this stage, ether the target was found or deduced from the extension
    print("{} A file matching {} was found".format(tag,target))
    datafile = tar.extractfile(target)

    return datafile


###----------------------------------------------------------------------------
def backup_file(filename,folder=None, dbg=False):
    """
    Copy a file to a result folder.
    If it already exists, make a backup with the date.

    Parameters
    ----------
    file : TYPE
        DESCRIPTION.
    folder : String, optional
        Output folder. The default is None.
    dbg : Boolean, optional
        If True, display messages. The default is False.

    Returns
    -------
    None.

    """
    """

    """
    import os
    import shutil
    import datetime

    # Create result folder if not exisitng
    if (not os.path.exists(folder)):
            if (dbg): print(" *** Creating output folder ",folder)
            os.makedirs(folder)

    output_file = folder+"/"+filename

    if os.path.exists(output_file):
        nw = datetime.datetime.now()
        output_file = output_file + "_" \
                                  + str(nw.hour) \
                                  + str(nw.minute) \
                                  + str(nw.second)

    shutil.copy(filename, output_file)
    if (dbg): print("   ----",filename," copied to ",output_file())

    return


