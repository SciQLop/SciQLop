import numpy as np

from SciQLop.components.scenes.boundary import RadialBoundary

_DP, _BZ = 2.0, 0.0   # nominal solar wind: Dp in nPa, IMF Bz in nT


class Shue1998(RadialBoundary):
    name, body, kind, frame = "shue1998", "earth", "magnetopause", "GSM"
    label = "Shue 1998 (Dp=2 nPa, Bz=0)"
    description = "Earth magnetopause, empirical, nominal solar wind."
    reference = "doi:10.1029/98JA01103"

    def radius(self, theta, phi, times):
        r0 = (10.22 + 1.29 * np.tanh(0.184 * (_BZ + 8.14))) * _DP ** (-1 / 6.6)
        alpha = (0.58 - 0.007 * _BZ) * (1 + 0.024 * np.log(_DP))
        with np.errstate(divide="ignore"):   # diverges at theta = 180 deg, cut by theta_max anyway
            return r0 * (2 / (1 + np.cos(theta))) ** alpha


class Jelinek2012BowShock(RadialBoundary):
    name, body, kind, frame = "jelinek2012", "earth", "bow_shock", "GSE"
    label = "Jelínek 2012 (Dp=2 nPa)"
    description = "Earth bow shock, THEMIS-based, nominal pressure; solar-wind aberration ignored."
    reference = "doi:10.1029/2011JA017252"

    def radius(self, theta, phi, times):
        r0 = 2 * 15.02 * _DP ** (-1 / 6.55)
        return r0 / (np.cos(theta) + np.sqrt(np.cos(theta) ** 2 + 1.17 ** 2 * np.sin(theta) ** 2))


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
    description = "Mercury magnetopause, MESSENGER fit, centred on the offset dipole."
    focus = (0.0, 0.0, 0.196)

    def radius(self, theta, phi, times):
        with np.errstate(divide="ignore"):   # diverges at theta = 180 deg, cut by theta_max
            return 1.45 * (2 / (1 + np.cos(theta))) ** 0.5


class Winslow2013BowShock(_Conic):
    name, body, kind, frame = "winslow2013_bs", "mercury", "bow_shock", "MESO"
    label, reference = "Winslow 2013 bow shock", "doi:10.1002/jgra.50237"
    description = "Mercury bow shock, MESSENGER conic fit."
    focus, semi_latus, eccentricity = (0.5, 0.0, 0.196), 2.75, 1.04
