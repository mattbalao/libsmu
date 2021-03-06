from __future__ import division, print_function

import random
import sys

import pytest

from pysmu import Session, Mode, WriteTimeout


@pytest.fixture(scope='function')
def session(request):
    """Default session adding all attached devices."""
    s = Session()
    yield s

    # force session destruction
    s._close()


@pytest.fixture(scope='function')
def device(session):
    """First device in the session fixture."""
    return session.devices[0]


@pytest.fixture(scope='function')
def chan_a(device):
    """Channel A of the first device in the session fixture."""
    return device.channels['A']


@pytest.fixture(scope='function')
def chan_b(device):
    """Channel B of the first device in the session fixture."""
    return device.channels['B']


def test_chan_write_timeout(chan_a, chan_b):
    """Performing multiple writes before starting a session causes write timeouts."""
    with pytest.raises(WriteTimeout):
        chan_a.mode = Mode.SVMI
        chan_a.sine(0, 5, 100, 0)
        chan_a.constant(2)

    with pytest.raises(WriteTimeout):
        chan_b.mode = Mode.SVMI
        chan_b.sine(0, 5, 100, 25)
        chan_b.constant(4)


def test_chan_mode(chan_a, chan_b):
    """Simple channel mode setting."""
    # channels start in HI_Z mode by default
    assert chan_a.mode == chan_b.mode == Mode.HI_Z

    # invalid mode assignment raises ValueError
    with pytest.raises(ValueError):
        chan_a.mode = 4

    # raw values can't be used for assignment, enum aliases must be used
    with pytest.raises(ValueError):
        chan_a.mode = 1

    chan_a.mode = chan_b.mode = Mode.SVMI
    assert chan_a.mode == chan_b.mode == Mode.SVMI


def test_chan_read(session, chan_a):
    """Simple channel data acquisition."""
    session.run(1000)
    samples = chan_a.read(1000, -1)
    assert len(samples) == 1000
    assert len(samples[0]) == 2


def test_chan_write(chan_a, chan_b):
    pass


def test_chan_get_samples(chan_a, chan_b):
    """Simple channel data acquisition via get_samples()."""
    samples = chan_a.get_samples(1000)
    assert len(samples) == 1000
    assert len(samples[0]) == 2


def test_chan_arbitrary(chan_a, chan_b):
    pass


def test_chan_constant(chan_a, chan_b):
    """Write a constant value to both channels of a device and verify reteurned data."""
    chan_a.mode = Mode.SVMI
    chan_a.constant(2)
    chan_b.mode = Mode.SVMI
    chan_b.constant(4)

    # verify sample values are near 2 for channel A
    samples = chan_a.get_samples(1000)
    assert len(samples) == 1000
    for x in samples:
        assert abs(round(x[0])) == 2

    # verify sample values are near 4 for channel B
    samples = chan_b.get_samples(1000)
    assert len(samples) == 1000
    for x in samples:
        assert abs(round(x[0])) == 4


def test_chan_sine(chan_a, chan_b, device):
    """Write a sine wave to both channels of a device and verify a matching, returned frequency."""
    try:
        import numpy as np
        from scipy import signal
    except ImportError:
        pytest.skip("test requires numpy and scipy installed")

    sys.stdout.write('\n')
    for _x in xrange(5):
        freq = random.randint(10, 100)
        print('testing frequency: {}'.format(freq))
        period = freq * 10
        num_samples = period * freq

        # write a sine wave to both channels, one as a voltage source and the
        # other as current
        chan_a.mode = Mode.SVMI
        chan_a.sine(chan_a.signal.min, chan_a.signal.max, period, -(period / 4))
        chan_b.mode = Mode.SIMV
        chan_b.sine(chan_b.signal.min, chan_b.signal.max, period, 0)

        chan_a_samples = []
        chan_b_samples = []

        # split data acquisition across multiple runs in order to test waveform continuity
        for i in xrange(10):
            samples = device.get_samples(period * freq / 10)
            chan_a_samples.extend([x[0][0] for x in samples])
            chan_b_samples.extend([x[1][1] for x in samples])
            assert len(chan_a_samples) == len(chan_b_samples) == (i + 1) * (period * freq / 10)

        assert len(chan_a_samples) == len(chan_b_samples) == num_samples

        # Verify the frequencies of the resulting waveforms
        hanning = signal.get_window('hanning', num_samples)
        chan_a_freqs, chan_a_psd = signal.welch(chan_a_samples, window=hanning, nperseg=num_samples)
        chan_b_freqs, chan_b_psd = signal.welch(chan_b_samples, window=hanning, nperseg=num_samples)
        assert np.argmax(chan_a_psd) == np.argmax(chan_b_psd)
        assert abs(freq - np.argmax(chan_a_psd)) <= 1
