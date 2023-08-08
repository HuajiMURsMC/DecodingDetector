from types import MethodType

from mcdreforged.api.types import PluginServerInterface
from mcdreforged.mcdr_server import MCDReforgedServer
from mcdreforged.utils.exception import DecodeError
from mcdreforged.constants import core_constant
from subprocess import TimeoutExpired

import charset_normalizer

backup = None


def my_receive(self: MCDReforgedServer):
    try:
        line_buf: bytes = next(iter(self.process.stdout))
    except StopIteration:  # server process has stopped
        for i in range(core_constant.WAIT_TIME_AFTER_SERVER_STDOUT_END_SEC):
            try:
                self.process.wait(1)
            except TimeoutExpired:
                self.logger.info(self.tr('mcdr_server.receive.wait_stop'))
            else:
                break
        else:
            self.logger.warning('The server is still not stopped after {}s after its stdout was closed, killing'.format(core_constant.WAIT_TIME_AFTER_SERVER_STDOUT_END_SEC))
            self.__kill_server()
        self.process.wait()
        return None
    else:
        try:
            try:
                line_text = line_buf.decode(getattr(self, 'detected_decoding', None) or self.decoding_method)
            except UnicodeDecodeError as e:
                if getattr(self, 'detected_decoding', None) is None:
                    if getattr(self, 'decdet_plugin_unloaded', None) is not None:
                        del self.decdet_plugin_unloaded
                        raise e
                    result = charset_normalizer.detect(line_buf)
                    self.logger.warning('It looks like the server is using a different encoding than the one specified in the config file.')
                    self.logger.warning('Detected: {}, confidence: {}'.format(result['encoding'], result['confidence']))
                    line_text = line_buf.decode(result['encoding'])
                    self.detected_decoding = result['encoding']
        except Exception as e:
            self.logger.error(self.tr('mcdr_server.receive.decode_fail', line_buf, e))
            raise DecodeError()
        return line_text.strip('\n\r')


def on_load(server: PluginServerInterface, old):
    global backup
    print("Patching MCDReforgedServer")
    mcdr_server = server._mcdr_server
    backup = mcdr_server._MCDReforgedServer__receive
    mcdr_server._MCDReforgedServer__receive = MethodType(my_receive, mcdr_server)


def on_unload(server: PluginServerInterface):
    global backup
    mcdr_server = server._mcdr_server
    if backup is not None:
        mcdr_server._MCDReforgedServer__receive = backup
    if getattr(mcdr_server, "detected_decoding", None) is not None:
        mcdr_server.decdet_plugin_unloaded = True
        del mcdr_server.detected_decoding
