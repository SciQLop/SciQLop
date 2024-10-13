from jupyter_client import KernelProvisionerBase

import logging
import json
import os

log = logging.getLogger(__name__)


# taken from here https://github.com/pyxll/pyxll-jupyter/blob/master/pyxll_jupyter/provisioning/existing.py

class SciQLopProvisioner(KernelProvisionerBase):  # type: ignore
    """
    """

    async def launch_kernel(self, cmd, **kwargs):
        # Connect to kernel started by PyXLL
        connection_file = os.environ["SCIQLOP_IPYTHON_CONNECTION_FILE"]
        if not os.path.abspath(connection_file):
            connection_dir = os.path.join(os.environ["APPDATA"], "jupyter", "runtime")
            connection_file = os.path.join(connection_dir, connection_file)

        if not os.path.exists(connection_file):
            log.warning(f"Jupyter connection file '{connection_file}' does not exist.")

        log.info(f'SciQLop IPython kernel = {connection_file}')
        with open(connection_file) as f:
            file_info = json.load(f)

        file_info["key"] = file_info["key"].encode()
        return file_info

    async def pre_launch(self, **kwargs):
        kwargs = await super().pre_launch(**kwargs)
        kwargs.setdefault('cmd', None)
        return kwargs

    @property
    def has_process(self) -> bool:
        return True

    async def poll(self):
        pass

    async def wait(self):
        pass

    async def send_signal(self, signum: int):
        pass

    async def kill(self, restart=False):
        if restart:
            log.warning("Cannot restart kernel running in SciQLop.")

    async def terminate(self, restart=False):
        if restart:
            log.warning("Cannot restart kernel running in SciQLop.")

    async def cleanup(self, restart):
        pass
