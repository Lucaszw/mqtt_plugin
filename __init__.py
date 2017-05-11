import logging

from microdrop.plugin_helpers import get_plugin_info
from microdrop.plugin_manager import (PluginGlobals, Plugin, IPlugin,
                                      implements)
import paho_mqtt_helpers as pmh
import path_helpers as ph

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

logger = logging.getLogger(__name__)


PluginGlobals.push_env('microdrop.managed')

class MqttPlugin(pmh.BaseMqttReactor, Plugin):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    version = __version__
    plugin_name = get_plugin_info(ph.path(__file__).parent).plugin_name

    def __init__(self):
        super(MqttPlugin, self).__init__()
        self.name = self.plugin_name

    ###########################################################################
    # MicroDrop pyutilib plugin handlers
    # ==================================
    def on_plugin_disable(self):
        """
        Handler called once the plugin instance is disabled.
        """
        # Stop MQTT reactor.
        self.stop()

    def on_plugin_enable(self):
        """
        Handler called once the plugin instance is enabled.
        """
        # Start MQTT reactor.
        self.start()


PluginGlobals.pop_env()
