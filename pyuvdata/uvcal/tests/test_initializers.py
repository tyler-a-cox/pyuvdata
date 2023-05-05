import re

import numpy as np
import pytest
from astropy.coordinates import EarthLocation

from pyuvdata.uvcal.initializers import new_uvcal, new_uvcal_from_uvdata
from pyuvdata.uvdata.initializers import new_uvdata


@pytest.fixture(scope="function")
def uvd_kw():
    return {
        "freq_array": np.linspace(100e6, 200e6, 10),
        "times": np.linspace(2459850, 2459851, 12),
        "antenna_positions": {
            0: [0.0, 0.0, 0.0],
            1: [0.0, 0.0, 1.0],
            2: [0.0, 0.0, 2.0],
        },
        "telescope_location": EarthLocation.from_geodetic(0, 0, 0),
        "telescope_name": "mock",
        "polarization_array": np.array([-5, -6, -7, -8]),
    }


@pytest.fixture(scope="function")
def uvc_only_kw():
    return {
        "cal_style": "redundant",
        "gain_convention": "multiply",
        "x_orientation": "n",
        "jones_array": "linear",
        "cal_type": "gain",
    }


@pytest.fixture(scope="function")
def uvc_kw(uvd_kw, uvc_only_kw):
    uvd_kw["time_array"] = uvd_kw["times"]
    del uvd_kw["times"]
    del uvd_kw["polarization_array"]
    return {**uvc_only_kw, **uvd_kw}


def test_new_uvcal_simplest(uvc_kw):
    uvc = new_uvcal(**uvc_kw)
    assert uvc.Nants_data == 3
    assert uvc.Nants_telescope == 3
    assert uvc.Nfreqs == 10
    assert uvc.Ntimes == 12


def test_new_uvcal_bad_inputs(uvc_kw):
    with pytest.raises(
        ValueError, match="The following ants are not in antenna_numbers"
    ):
        new_uvcal(ant_array=[0, 1, 2, 3], **uvc_kw)

    with pytest.raises(
        ValueError,
        match=re.escape(
            "If cal_style is 'sky', ref_antenna_name, sky_catalog and sky_field must "
            "all be provided"
        ),
    ):
        new_uvcal(
            cal_style="sky", **{k: v for k, v in uvc_kw.items() if k != "cal_style"}
        )

    with pytest.raises(
        ValueError, match="cal_style must be 'redundant' or 'sky'\\, got"
    ):
        new_uvcal(
            cal_style="wrong",
            ref_antenna_name="mock",
            sky_catalog="mock",
            **{k: v for k, v in uvc_kw.items() if k != "cal_style"}
        )

    with pytest.raises(ValueError, match="Unrecognized keyword argument"):
        new_uvcal(bad_kwarg=True, **uvc_kw)

    with pytest.raises(
        ValueError, match=re.escape("Provide *either* freq_range *or* freq_array")
    ):
        new_uvcal(freq_range=[100e6, 200e6], **uvc_kw)

    with pytest.raises(ValueError, match="You must provide either freq_array"):
        new_uvcal(**{k: v for k, v in uvc_kw.items() if k != "freq_array"})

    with pytest.raises(ValueError, match="cal_type must be either 'gain' or 'delay'"):
        new_uvcal(
            cal_type="wrong",
            freq_range=[150e6, 180e6],
            **{k: v for k, v in uvc_kw.items() if k not in ("freq_array", "cal_type")}
        )


def test_new_uvcal_jones_array(uvc_kw):
    uvc = {k: v for k, v in uvc_kw.items() if k != "jones_array"}

    lin = new_uvcal(jones_array="linear", **uvc)
    assert lin.Njones == 4

    circ = new_uvcal(jones_array="circular", **uvc)
    assert circ.Njones == 4
    assert np.allclose(circ.jones_array, np.array([-1, -2, -3, -4]))

    custom = new_uvcal(jones_array=np.array([-1, -3]), **uvc)
    assert custom.Njones == 2


def test_new_uvcal_set_sky(uvc_kw):
    uvc = {k: v for k, v in uvc_kw.items() if k != "cal_style"}
    sk = new_uvcal(
        cal_style="sky",
        ref_antenna_name="mock",
        sky_catalog="mock",
        sky_field="mock",
        **uvc
    )
    assert sk.cal_style == "sky"
    assert sk.ref_antenna_name == "mock"
    assert sk.sky_catalog == "mock"
    assert sk.sky_field == "mock"


def test_new_uvcal_set_extra_keywords(uvc_kw):
    uvc = new_uvcal(extra_keywords={"test": "test", "test2": "test2"}, **uvc_kw)
    assert uvc.extra_keywords["test"] == "test"
    assert uvc.extra_keywords["test2"] == "test2"


def test_new_uvcal_set_empty(uvc_kw):
    uvc = new_uvcal(empty=True, **uvc_kw)
    assert uvc.flag_array.dtype == bool


def test_new_uvcal_set_delay(uvc_kw):
    uvc = {k: v for k, v in uvc_kw.items() if k not in ("freq_array", "cal_type")}
    new = new_uvcal(
        delay_array=np.linspace(1, 10, 10),
        freq_range=[150e6, 180e6],
        wide_band=False,
        empty=True,
        **uvc
    )
    assert new.cal_type == "delay"
    assert new.quality_array.shape[1] == new.Nspws


def test_new_uvcal_from_uvdata(uvd_kw, uvc_only_kw):
    uvd = new_uvdata(**uvd_kw)

    uvc = new_uvcal_from_uvdata(uvd, **uvc_only_kw)

    assert np.all(uvc.time_array == uvd_kw["times"])
    assert np.all(uvc.freq_array == uvd_kw["freq_array"])
    assert uvc.telescope_name == uvd_kw["telescope_name"]

    uvc = new_uvcal_from_uvdata(uvd, time_array=uvd_kw["times"][:-1], **uvc_only_kw)
    assert np.all(uvc.time_array == uvd_kw["times"][:-1])

    uvc = new_uvcal_from_uvdata(
        uvd, freq_array=uvd_kw["freq_array"][:-1], **uvc_only_kw
    )
    assert np.all(uvc.freq_array == uvd_kw["freq_array"][:-1])

    uvc = new_uvcal_from_uvdata(
        uvd,
        antenna_positions={
            0: uvd_kw["antenna_positions"][0],
            1: uvd_kw["antenna_positions"][1],
        },
        **uvc_only_kw
    )

    assert np.all(uvc.antenna_positions[0] == uvd_kw["antenna_positions"][0])
    assert len(uvc.antenna_positions) == 2
