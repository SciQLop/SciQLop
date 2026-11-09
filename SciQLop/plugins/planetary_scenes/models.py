import numpy as np

from SciQLop.components.scenes.boundary import RadialBoundary

from .solar_wind import BZ_GSM, PRESSURE, upstream

_DP, _BZ = 2.0, 0.0   # nominal solar wind: Dp in nPa, IMF Bz in nT


def _shue(theta, dp, bz):
    r0 = (10.22 + 1.29 * np.tanh(0.184 * (bz + 8.14))) * dp ** (-1 / 6.6)
    alpha = (0.58 - 0.007 * bz) * (1 + 0.024 * np.log(dp))
    with np.errstate(divide="ignore"):   # diverges at theta = 180 deg, cut by theta_max anyway
        return r0 * (2 / (1 + np.cos(theta))) ** alpha


def _jelinek(theta, dp):
    r0 = 2 * 15.02 * dp ** (-1 / 6.55)
    with np.errstate(divide="ignore"):   # diverges at theta = 180 deg, cut by theta_max anyway
        return r0 / (np.cos(theta) + np.sqrt(np.cos(theta) ** 2 + 1.17 ** 2 * np.sin(theta) ** 2))


class Shue1998(RadialBoundary):
    name, body, kind, frame = "shue1998", "earth", "magnetopause", "GSM"
    label = "Shue 1998 (Dp=2 nPa, Bz=0)"
    description = "Earth magnetopause, empirical, nominal solar wind; fitted in an aberrated frame (~4 deg), aberration ignored."
    reference = "doi:10.1029/98JA01103"

    def radius(self, theta, phi, times):
        return _shue(theta, _DP, _BZ)


class Shue1998Omni(Shue1998):
    name, label = "shue1998_omni", "Shue 1998 (OMNI)"
    description = ("Earth magnetopause, empirical, driven by OMNI 1-min pressure and IMF Bz (GSM); a time without "
                   "OMNI data has no section. Fitted in an aberrated frame (~4 deg), aberration ignored.")

    def radius(self, theta, phi, times):
        return _shue(theta, upstream(PRESSURE, times), upstream(BZ_GSM, times))


class Jelinek2012BowShock(RadialBoundary):
    name, body, kind, frame = "jelinek2012", "earth", "bow_shock", "GSE"
    label = "Jelínek 2012 (Dp=2 nPa)"
    description = "Earth bow shock, THEMIS-based, nominal pressure; solar-wind aberration ignored."
    reference = "doi:10.1029/2011JA017252"

    def radius(self, theta, phi, times):
        return _jelinek(theta, _DP)


class Jelinek2012BowShockOmni(Jelinek2012BowShock):
    name, label = "jelinek2012_omni", "Jelínek 2012 (OMNI)"
    description = ("Earth bow shock, THEMIS-based, driven by OMNI 1-min pressure; a time without OMNI data has "
                   "no section. Solar-wind aberration ignored.")

    def radius(self, theta, phi, times):
        return _jelinek(theta, upstream(PRESSURE, times))


class _Conic(RadialBoundary):
    semi_latus: float
    eccentricity: float

    def radius(self, theta, phi, times):
        with np.errstate(divide="ignore"):   # e >= 1 diverges past the asymptote, cut by theta_max
            return self.semi_latus / (1 + self.eccentricity * np.cos(theta))


class Vignes2000BowShock(_Conic):
    name, body, kind, frame = "vignes2000_bs", "mars", "bow_shock", "MSO"
    label, reference = "Vignes 2000 bow shock", "doi:10.1029/1999GL010703"
    description = "Mars bow shock, conic fit to MGS data; aberration ignored."
    focus, semi_latus, eccentricity = (0.64, 0.0, 0.0), 2.04, 1.03


class Vignes2000MPB(_Conic):
    name, body, kind, frame = "vignes2000_mpb", "mars", "mpb", "MSO"
    label, reference = "Vignes 2000 MPB", "doi:10.1029/1999GL010703"
    description = "Mars magnetic pileup boundary, conic fit to MGS data; aberration ignored."
    focus, semi_latus, eccentricity = (0.78, 0.0, 0.0), 0.96, 0.90


class Winslow2013Magnetopause(RadialBoundary):
    name, body, kind, frame = "winslow2013_mp", "mercury", "magnetopause", "MESO"
    label, reference = "Winslow 2013 magnetopause", "doi:10.1002/jgra.50237"
    description = "Mercury magnetopause, MESSENGER fit, centred on the offset dipole; fitted in an aberrated frame (~6-8 deg), aberration ignored."
    focus = (0.0, 0.0, 0.196)

    def radius(self, theta, phi, times):
        with np.errstate(divide="ignore"):   # diverges at theta = 180 deg, cut by theta_max
            return 1.45 * (2 / (1 + np.cos(theta))) ** 0.5


class Winslow2013BowShock(_Conic):
    name, body, kind, frame = "winslow2013_bs", "mercury", "bow_shock", "MESO"
    label, reference = "Winslow 2013 bow shock", "doi:10.1002/jgra.50237"
    description = "Mercury bow shock, MESSENGER conic fit; fitted in an aberrated frame (~6-8 deg), aberration ignored."
    focus, eccentricity = (0.5, 0.0, 0.196), 1.04
    semi_latus = 2.75 * eccentricity   # source form r = p*e / (1 + e cos(theta)), p = 2.75
