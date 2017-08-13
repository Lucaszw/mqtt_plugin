import json
import logging

from microdrop.app_context import get_app, get_hub_uri
from microdrop.plugin_helpers import get_plugin_info
from microdrop.plugin_manager import (PluginGlobals, Plugin, IPlugin,
                                      implements, emit_signal)
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
        self.start()
        self.mqtt_client.subscribe("microdrop/dmf-device-ui/change-step")
        self.mqtt_client.subscribe("microdrop/dmf-device-ui/delete-step")
        self.mqtt_client.subscribe("microdrop/dmf-device-ui/insert-step")
        self.mqtt_client.subscribe("microdrop/dmf-device-ui/change-protocol-state")

    ###########################################################################
    # MicroDrop pyutilib plugin handlers
    # ==================================
    def on_message(self, client, userdata, msg):
        '''
        Callback for when a ``PUBLISH`` message is received from the broker.
        '''
        if msg.topic == 'microdrop/dmf-device-ui/change-step':
            self.change_step(json.loads(msg.payload))
        if msg.topic == "microdrop/dmf-device-ui/delete-step":
            self.delete_step(json.loads(msg.payload))
        if msg.topic == "microdrop/dmf-device-ui/insert-step":
            self.insert_step(json.loads(msg.payload))
        if msg.topic == "microdrop/dmf-device-ui/change-protocol-state":
            self.change_protocol_state(json.loads(msg.payload))

    def on_plugin_disable(self):
        """
        Handler called once the plugin instance is disabled.
        """
        # Stop MQTT reactor.
        # TODO: Currently, not stopping MQTT after termination, possibly
        # unsafe?
        # self.stop()

    def on_plugin_enable(self):
        """
        Handler called once the plugin instance is enabled.
        """
        # TODO: When converting Protocol Controller to plugin, switch to
        #       having on_protocol_pause execute on pluign enabled
        self.mqtt_client.publish("microdrop/mqtt-plugin/protocol-state",
                                 json.dumps("paused"), retain=True)

    def on_protocol_run(self):
        self.mqtt_client.publish("microdrop/mqtt-plugin/protocol-state",
                                 json.dumps("running"), retain=True)

    def on_protocol_pause(self):
        self.mqtt_client.publish("microdrop/mqtt-plugin/protocol-state",
                                 json.dumps("paused"), retain=True)

    def on_step_swapped(self, old_step_number, step_number):
        """
        Called when protocol controller swaps steps
        """
        self.mqtt_client.publish("microdrop/mqtt-plugin/step-swapped",
                     json.dumps(step_number), retain=True)

    def change_step(self,step_number):
        app = get_app()
        app.protocol.goto_step(step_number)

    def delete_step(self, step_number):
        app = get_app()
        app.protocol.delete_step(step_number)

    def insert_step(self, step_number):
        app = get_app()
        app.protocol.insert_step(step_number)
        app.protocol.next_step()
        self.mqtt_client.publish("microdrop/mqtt-plugin/step-inserted",
                                 json.dumps(app.protocol.current_step_number))

    def change_protocol_state(self, step):
        # TODO: Think about turning protocol controller into its own plugin
        app = get_app()

        if app.running:
            app.protocol.current_step_attempt = 0
            app.running = False
            emit_signal("on_run_protocol", [None, None])
        else:
            emit_signal("on_run_protocol", [None, None])

PluginGlobals.pop_env()
