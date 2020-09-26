import time
import logging
import os
import unittest

from yurt import vm, lxc, util
from yurt.exceptions import YurtException

logging.basicConfig(format='%(levelname)s: %(message)s', level="INFO")


class YurtTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.discard_vm = os.environ.get(
            "YURT_TEST_DISCARD_VM_POLICY") == "discard"

        if vm.state() == vm.State.NotInitialized:
            vm.init()
            logging.info("Waiting for VM registration...")
            time.sleep(3)

        if vm.state() == vm.State.Stopped:
            vm.start()
            lxc.configure_lxd()

        def check_if_running():
            if vm.state() != vm.State.Running:
                raise YurtException("VM Not running")
        util.retry(check_if_running)

    @classmethod
    def tearDownClass(cls):
        if cls.discard_vm:
            vm.stop()
            time.sleep(10)   # TODO 164
            vm.destroy()
