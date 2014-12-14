/* -*- c++ -*-
 * Copyright (c) 2012-2014 by the GalSim developers team on GitHub
 * https://github.com/GalSim-developers
 *
 * This file is part of GalSim: The modular galaxy image simulation toolkit.
 * https://github.com/GalSim-developers/GalSim
 *
 * GalSim is free software: redistribution and use in source and binary forms,
 * with or without modification, are permitted provided that the following
 * conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this
 *    list of conditions, and the disclaimer given in the accompanying LICENSE
 *    file.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions, and the disclaimer given in the documentation
 *    and/or other materials provided with the distribution.
 */

//#define DEBUGLOGGING

#include "SBSpergel.h"
#include "SBSpergelImpl.h"
#include <boost/math/special_functions/bessel.hpp>
#include <boost/math/special_functions/gamma.hpp>
#include "Solve.h"

// Define this variable to find azimuth (and sometimes radius within a unit disc) of 2d photons by
// drawing a uniform deviate for theta, instead of drawing 2 deviates for a point on the unit
// circle and rejecting corner photons.
// The relative speed of the two methods was tested as part of issue #163, and the results
// are collated in devutils/external/time_photon_shooting.
// The conclusion was that using sin/cos was faster for icpc, but not g++ or clang++.
#ifdef _INTEL_COMPILER
#define USE_COS_SIN
#endif

#ifdef DEBUGLOGGING
#include <fstream>
#endif

namespace galsim {

    SBSpergel::SBSpergel(double nu, double size, RadiusType rType, double flux,
                         const GSParamsPtr& gsparams) :
        SBProfile(new SBSpergelImpl(nu, size, rType, flux, gsparams)) {}

    SBSpergel::SBSpergel(const SBSpergel& rhs) : SBProfile(rhs) {}

    SBSpergel::~SBSpergel() {}

    double SBSpergel::getNu() const
    {
        assert(dynamic_cast<const SBSpergelImpl*>(_pimpl.get()));
        return static_cast<const SBSpergelImpl&>(*_pimpl).getNu();
    }

    double SBSpergel::getScaleRadius() const
    {
        assert(dynamic_cast<const SBSpergelImpl*>(_pimpl.get()));
        return static_cast<const SBSpergelImpl&>(*_pimpl).getScaleRadius();
    }

    LRUCache<boost::tuple< double, GSParamsPtr >, SpergelInfo> SBSpergel::SBSpergelImpl::cache(
        sbp::max_spergel_cache);

    class SpergelIntegratedFlux
    {
    public:
        SpergelIntegratedFlux(double nu, double flux_frac=0.0) : _nu(nu), _target(flux_frac) {}

        double operator()(double u) const
        // Return flux integrated up to radius `u` in units of r0, minus `flux_frac`
        // (i.e., make a residual so this can be used to search for a target flux.
        {
            double fnup1 = std::pow(u / 2., _nu+1)
                * boost::math::cyl_bessel_k(_nu+1, u)
                / boost::math::tgamma(_nu + 2.);
            double f = 1.0 - 2.0 * (1+_nu)*fnup1;
            return f - _target;
        }
    private:
        double _nu;
        double _target;
    };

    double SBSpergel::SBSpergelImpl::calculateFluxRadius(const double& flux_frac) const
    {
        // Calcute r such that L(r/r0) / L_tot == flux_frac

        // These seem to bracket pretty much every reasonable possibility
        // that I checked in Mathematica.
        double z1=0.001;
        double z2=25.0;
        SpergelIntegratedFlux func(_nu, flux_frac);
        Solve<SpergelIntegratedFlux> solver(func, z1, z2);
        solver.setMethod(Brent);
        double R = solver.root();
        dbg<<"flux_frac = "<<flux_frac<<std::endl;
        dbg<<"r/r0 = "<<R<<std::endl;
        return R;
    }

    SBSpergel::SBSpergelImpl::SBSpergelImpl(double nu, double size, RadiusType rType,
                                            double flux, const GSParamsPtr& gsparams) :
        SBProfileImpl(gsparams),
        _nu(nu), _flux(flux),
        _stepk(0.0), _maxk(0.0),
        _info(cache.get(boost::make_tuple(_nu, this->gsparams.duplicate())))
    {
        dbg<<"Start SBSpergel constructor:\n";
        dbg<<"nu = "<<_nu<<std::endl;
        dbg<<"flux = "<<_flux<<std::endl;

        _flux_over_2pi = _flux / (2. * M_PI);

        _cnu = calculateFluxRadius(0.5);

        switch(rType) {
        case HALF_LIGHT_RADIUS:
            {
                _re = size;
                _r0 = _re / _cnu;
            }
            break;
        case SCALE_RADIUS:
            {
                _r0 = size;
                _re = _r0 * _cnu;
            }
            break;
        }

        _r0_sq = _r0 * _r0;
        _inv_r0 = 1. / _r0;
        _norm = _flux / _r0_sq / boost::math::tgamma(_nu + 1.);

        dbg<<"scale radius = "<<_r0<<std::endl;
        dbg<<"C_nu = "<<_cnu<<std::endl;
        dbg<<"HLR = "<<_re<<std::endl;
    }

    double SBSpergel::SBSpergelImpl::maxK() const
    {
        if(_maxk == 0.) {
            // Solving (1+k^2)^(-1-nu) = maxk_threshold for k
            // exact:
            //_maxk = std::sqrt(std::pow(gsparams->maxk_threshold, -1./(1+_nu))-1.0) * _inv_r0;
            // approximate 1+k^2 ~ k^2 => good enough:
            _maxk = std::pow(gsparams->maxk_threshold, -1./(2*(1+_nu))) * _inv_r0;
        }
        return _maxk;
    }

    double SBSpergel::SBSpergelImpl::stepK() const
    {
        if (_stepk == 0.) {
            double R = calculateFluxRadius(1.0 - gsparams->folding_threshold);
            // Go to at least 5*re
            R = std::max(R,gsparams->stepk_minimum_hlr/_cnu);
            _stepk = M_PI / R * _inv_r0;
        }
        return _stepk;
    }

    // Equations (3, 4) of Spergel (2010)
    double SBSpergel::SBSpergelImpl::xValue(const Position<double>& p) const
    {
        double r = sqrt(p.x * p.x + p.y * p.y);
        double u = r * _inv_r0;
        double f = boost::math::cyl_bessel_k(_nu, u) * std::pow(u / 2., _nu);
        return _norm * f;
    }

    // Equation (2) of Spergel (2010)
    std::complex<double> SBSpergel::SBSpergelImpl::kValue(const Position<double>& k) const
    {
        double ksq = (k.x*k.x + k.y*k.y)*_r0_sq;
        return _flux / std::pow(1. + ksq, 1. + _nu);
    }

    SpergelInfo::SpergelInfo(double nu, const GSParamsPtr& gsparams) :
        _nu(nu), _gsparams(gsparams),
        _maxk(0.), _stepk(0.), _re(0.), _flux(0.)
    {
        dbg<<"Start SpergelInfo constructor for nu = "<<_nu<<std::endl;

        if (_nu < sbp::minimum_spergel_nu || _nu > sbp::maximum_spergel_nu)
            throw SBError("Requested Spergel index out of range");
    }

    class SpergelRadialFunction: public FluxDensity
    {
    public:
        SpergelRadialFunction(double nu): _nu(nu) {}
        double operator()(double r) const { return std::exp(-std::pow(r,_nu)) * boost::math::cyl_bessel_k(_nu, r); }
    private:
        double _nu;
    };

    boost::shared_ptr<PhotonArray> SpergelInfo::shoot(int N, UniformDeviate ud) const
    {
        dbg<<"SpergelInfo shoot: N = "<<N<<std::endl;
        dbg<<"Target flux = 1.0\n";

        if (!_sampler) {
            // Set up the classes for photon shooting
            _radial.reset(new SpergelRadialFunction(_nu));
            std::vector<double> range(2,0.);
            //double shoot_maxr = calculateMissingFluxRadius(_gsparams->shoot_accuracy);
            double shoot_maxr = 1.0;
            range[1] = shoot_maxr;
            _sampler.reset(new OneDimensionalDeviate( *_radial, range, true, _gsparams));
        }

        assert(_sampler.get());
        boost::shared_ptr<PhotonArray> result = _sampler->shoot(N,ud);
        dbg<<"SpergelInfo Realized flux = "<<result->getTotalFlux()<<std::endl;
        return result;
    }

    boost::shared_ptr<PhotonArray> SBSpergel::SBSpergelImpl::shoot(int N, UniformDeviate ud) const
    {
        dbg<<"Spergel shoot: N = "<<N<<std::endl;
        dbg<<"Target flux = "<<getFlux()<<std::endl;
        // Get photons from the SpergelInfo structure, rescale flux and size for this instance
        boost::shared_ptr<PhotonArray> result = _info->shoot(N,ud);
        result->scaleFlux(_shootnorm);
        result->scaleXY(_r0);
        dbg<<"Spergel Realized flux = "<<result->getTotalFlux()<<std::endl;
        return result;
    }
}