import os
import platform

def pytest_generate_tests(metafunc):
    if platform.system() == 'Linux':
        os.environ['QT_QPA_PLATFORM'] = 'xcb'