# Copyright (c) 2012-2018 by the GalSim developers team on GitHub
# https://github.com/GalSim-developers
#
# This file is part of GalSim: The modular galaxy image simulation toolkit.
# https://github.com/GalSim-developers/GalSim
#
# GalSim is free software: redistribution and use in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions, and the disclaimer given in the accompanying LICENSE
#    file.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions, and the disclaimer given in the documentation
#    and/or other materials provided with the distribution.
#

from __future__ import print_function
import numpy as np
import os
import sys

import galsim
from galsim.errors import (
    GalSimValueError,
    GalSimRangeError,
    GalSimIncompatibleValuesError,
)
from galsim_test_helpers import *


@timer
def test_randwalk_defaults():
    """
    Create a random walk galaxy and test that the getters work for
    default inputs
    """

    # try constructing with mostly defaults
    npoints=100
    hlr = 8.0
    rng = galsim.BaseDeviate(1234)
    rw=galsim.RandomWalk(npoints, half_light_radius=hlr, rng=rng)

    assert rw.npoints==npoints,"expected npoints==%d, got %d" % (npoints, rw.npoints)
    assert rw.input_half_light_radius==hlr,\
        "expected hlr==%g, got %g" % (hlr, rw.input_half_light_radius)

    nobj=len(rw.points)
    assert nobj == npoints,"expected %d objects, got %d" % (npoints, nobj)

    pts=rw.points
    assert pts.shape == (npoints,2),"expected (%d,2) shape for points, got %s" % (npoints, pts.shape)
    np.testing.assert_almost_equal(rw.centroid.x, np.mean(pts[:,0]))
    np.testing.assert_almost_equal(rw.centroid.y, np.mean(pts[:,1]))

    gsp = galsim.GSParams(xvalue_accuracy=1.e-8, kvalue_accuracy=1.e-8)
    rw2 = galsim.RandomWalk(npoints, half_light_radius=hlr, rng=rng, gsparams=gsp)
    assert rw2 != rw
    assert rw2 == rw.withGSParams(gsp)

    # Run some basic tests of correctness
    psf = galsim.Gaussian(sigma=0.8)
    conv = galsim.Convolve(rw, psf)
    check_basic(conv, "RandomWalk")
    im = galsim.ImageD(64,64, scale=0.5)
    do_shoot(conv, im, "RandomWalk")
    do_kvalue(conv, im, "RandomWalk")
    do_pickle(rw)
    do_pickle(conv)


@timer
def test_randwalk_valid_inputs():
    """
    Create a random walk galaxy and test that the getters work for
    valid non-default inputs
    """

    # try constructing with mostly defaults
    npoints=100
    hlr = 8.0
    flux = 3.5

    seed=35
    rng=galsim.UniformDeviate(seed)

    args = (npoints,)
    kw1 = {'half_light_radius':hlr,'flux':flux,'rng':rng}
    prof=galsim.Exponential(half_light_radius=hlr, flux=flux)
    kw2 = {'profile':prof, 'rng':rng}

    # version of profile with a transformation
    prof=galsim.Exponential(half_light_radius=hlr, flux=flux)
    prof=prof.shear(g1=-0.05,g2=0.025)
    kw3 = {'profile':prof, 'rng':rng}


    for kw in (kw1, kw2, kw3):
        rw=galsim.RandomWalk(*args, **kw)

        assert rw.npoints==npoints,"expected npoints==%d, got %d" % (npoints, rw.npoints)

        assert rw.flux==flux,\
            "expected flux==%g, got %g" % (flux, rw.flux)

        if kw is not kw3:
            # only test if not a transformation object
            assert rw.input_half_light_radius==hlr,\
                "expected hlr==%g, got %g" % (hlr, rw.input_half_light_radius)

        pts=rw.points
        nobj=len(pts)
        assert nobj == npoints==npoints,"expected %d objects, got %d" % (npoints, nobj)

        pts=rw.points
        assert pts.shape == (npoints,2),"expected (%d,2) shape for points, got %s" % (npoints, pts.shape)

@timer
def test_randwalk_invalid_inputs():
    """
    Create a random walk galaxy and test that the the correct exceptions
    are raised for invalid inputs
    """

    npoints=100
    hlr = 8.0
    flux = 1.0

    # try sending wrong type for npoints
    with assert_raises(GalSimValueError):
        galsim.RandomWalk('blah', half_light_radius=1, flux=3)

    # try sending neither profile or hlr
    with assert_raises(GalSimIncompatibleValuesError):
        galsim.RandomWalk(npoints)

    # try with rng wrong type
    with assert_raises(TypeError):
        galsim.RandomWalk(npoints, half_light_radius=hlr, rng=37)

    # wrong type for profile
    with assert_raises(GalSimIncompatibleValuesError):
        galsim.RandomWalk(npoints, profile=3.5)

    # wrong type for npoints
    npoints_bad=[35]
    with assert_raises(TypeError):
        galsim.RandomWalk(npoints_bad, half_light_radius=hlr)

    # wrong type for hlr
    with assert_raises(GalSimRangeError):
        galsim.RandomWalk(npoints, half_light_radius=-1.5)

    # wrong type for flux
    with assert_raises(TypeError):
        galsim.RandomWalk(npoints, flux=[3.5], half_light_radius=hlr)

    # sending flux with a profile
    prof=galsim.Exponential(half_light_radius=hlr, flux=2.0)
    with assert_raises(GalSimIncompatibleValuesError):
        galsim.RandomWalk(npoints, flux=flux, profile=prof)

    # sending hlr with a profile
    with assert_raises(GalSimIncompatibleValuesError):
        galsim.RandomWalk(npoints, half_light_radius=3, profile=prof)


    # bad value for npoints
    npoints_bad=-35
    with assert_raises(GalSimRangeError):
        galsim.RandomWalk(npoints_bad, half_light_radius=hlr)

    # bad value for hlr
    with assert_raises(GalSimRangeError):
        galsim.RandomWalk(npoints, half_light_radius=-1.5)

    # negative flux
    with assert_raises(GalSimRangeError):
        galsim.RandomWalk(npoints, flux=-35.0, half_light_radius=hlr)


@timer
def test_randwalk_repr():
    """
    test the repr and str work, and that a new object can be created
    using eval
    """

    npoints=100
    hlr = 8.0
    flux=1
    rw1=galsim.RandomWalk(
        npoints,
        half_light_radius=hlr,
        flux=flux,
    )
    rw2=galsim.RandomWalk(
        npoints,
        profile=galsim.Exponential(half_light_radius=hlr, flux=flux),
    )

    for rw in (rw1, rw2):


        # just make sure str() works, don't require eval to give
        # a consistent object back
        st=str(rw)

        # require eval(repr(rw)) to give a consistent object back

        new_rw = eval(repr(rw))

        assert new_rw.npoints == rw.npoints,\
            "expected npoints=%d got %d" % (rw.npoints,new_rw.npoints)

        mess="expected input_half_light_radius=%.16g got %.16g"
        assert new_rw.input_half_light_radius == rw.input_half_light_radius,\
            mess % (rw.input_half_light_radius,new_rw.input_half_light_radius)
        assert new_rw.flux == rw.flux,\
            "expected flux=%.16g got %.16g" % (rw.flux,new_rw.flux)

@timer
def test_randwalk_config():
    """
    test we get the same object using a configuration and the
    explicit constructor
    """

    hlr=2.0
    flux=np.pi
    gal_config1 = {
        'type':'RandomWalk',
        'npoints':100,
        'half_light_radius':hlr,
        'flux':flux,
    }
    gal_config2 = {
        'type':'RandomWalk',
        'npoints':150,
        'profile': {
            'type': 'Exponential',
            'half_light_radius': hlr,
            'flux': flux,
        }
    }

    for gal_config in (gal_config1, gal_config2):
        config={
            'gal':gal_config,
            'rng':galsim.BaseDeviate(31415),
        }

        rwc = galsim.config.BuildGSObject(config, 'gal')[0]
        print(repr(rwc._profile))

        rw = galsim.RandomWalk(
            gal_config['npoints'],
            half_light_radius=hlr,
            flux=flux,
        )

        assert rw.npoints==rwc.npoints,\
            "expected npoints==%d, got %d" % (rw.npoints, rwc.npoints)

        assert rw.input_half_light_radius==rwc.input_half_light_radius,\
            "expected hlr==%g, got %g" % (rw.input_half_light_radius, rw.input_half_light_radius)

        nobj=len(rw.points)
        nobjc=len(rwc.points)
        assert nobj==nobjc,"expected %d objects, got %d" % (nobj,nobjc)

        pts=rw.points
        ptsc=rwc.points
        assert (pts.shape == ptsc.shape),\
                "expected %s shape for points, got %s" % (pts.shape,ptsc.shape)


@timer
def test_randwalk_hlr():
    """
    Create a random walk galaxy and test that the half light radius
    is consistent with the requested value

    Note for DeV profile we don't test npoints=3 because it fails
    """

    # for checking accuracy, we need expected standard deviation of
    # the result
    interp_npts = np.array([6,7,8,9,10,15,20,30,50,75,100,150,200,500,1000])
    interp_hlr  = np.array([7.511,7.597,7.647,7.68,7.727,7.827,7.884,7.936,7.974,8.0,8.015,8.019,8.031,8.027,8.043])/8.0
    interp_std = np.array([2.043,2.029,1.828,1.817,1.67,1.443,1.235,1.017,0.8046,0.6628,0.5727,0.4703,0.4047,0.255,0.1851])/8.0


    hlr = 8.0

    # test these npoints
    npt_vals=[3, 10, 30, 60, 100, 1000]

    # should be within 5 sigma
    nstd=5

    # number of trials
    ntrial_vals=[100]*len(npt_vals)

    profs = [
        galsim.Gaussian(half_light_radius=hlr),
        galsim.Exponential(half_light_radius=hlr),
        galsim.DeVaucouleurs(half_light_radius=hlr),
    ]
    for prof in profs:
        for ipts,npoints in enumerate(npt_vals):

            # DeV profile will fail for npoints==3
            if isinstance(prof,galsim.DeVaucouleurs) and npoints==3:
                continue

            ntrial=ntrial_vals[ipts]

            hlr_calc=np.zeros(ntrial)
            for i in range(ntrial):
                #rw=galsim.RandomWalk(npoints, hlr)
                rw=galsim.RandomWalk(npoints, profile=prof)
                hlr_calc[i] = rw.calculateHLR()

            mn=hlr_calc.mean()

            std_check=np.interp(npoints, interp_npts, interp_std*hlr)
            mess="hlr for npoints: %d outside of expected range" % npoints
            assert abs(mn-hlr) < nstd*std_check, mess

if __name__ == "__main__":
    test_randwalk_defaults()
    test_randwalk_valid_inputs()
    test_randwalk_invalid_inputs()
    test_randwalk_hlr()
    test_randwalk_repr()
    test_randwalk_config()
