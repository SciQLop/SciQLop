import os
import platform

def pytest_generate_tests(metafunc):
    if platform.system() == 'Linux':
        os.environ['QT_QPA_PLATFORM'] = 'xcb'


def pytest_configure(config):
    if platform.system() == 'Linux':
        config.option.xvfb_xauth = True
        config.option.xvfb_width = 2560
        config.option.xvfb_height = 1440