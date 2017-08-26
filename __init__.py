import atexit
import json
import logging

from microdrop.app_context import get_app, get_hub_uri
from microdrop.plugin_helpers import get_plugin_info

from microdrop.plugin_manager import (PluginGlobals, Plugin, IPlugin,
                                      implements, emit_signal)
from microdrop.protocol import protocol_from_dict

from zmq_plugin.schema import pandas_object_hook, PandasJsonEncoder
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
        self._props = {"steps": None, "protocol": None, "step_number": None}

    @property
    def steps(self):
        return self._props["steps"]

    @steps.setter
    def steps(self, value):
        self._props["steps"] = value
        app = get_app()

        if app.protocol is None: return

        enabled_plugins = get_service_names(env='microdrop.managed') + \
            get_service_names('microdrop')

        print "ENABLED PLUGINS:::"
        print enabled_plugins

        for i, s in enumerate(self.steps):

            if (i >= len(app.protocol.steps)):
                app.protocol.insert_step(i-1)

            step = app.protocol.steps[i]
            for plugin_name, item in s.iteritems():
                if plugin_name in enabled_plugins:
                    step.set_data(plugin_name, item)
                    emit_signal('on_step_options_changed', [plugin_name, i], interface=IPlugin)

        # If self.steps is shorter then protocol steps, delete the last one
        if len(self.steps) < len(app.protocol.steps):
            app.protocol.delete_step(len(app.protocol.steps)-1)

        self.mqtt_client.publish("microdrop/mqtt-plugin/steps", app.protocol.to_json())

    @property
    def step_number(self):
        return self._props["step_number"]

    @step_number.setter
    def step_number(self, value):
        app = get_app()
        if app.protocol is None: return
        # TODO: Handle what should happen if new step number out of reach
        self._props["step_number"] = value
        app.protocol.goto_step(value)

    @property
    def protocol(self):
        return self._props["protocol"]

    @protocol.setter
    def protocol(self, value):
        self._props["protocol"] = value
        app = get_app()
        protocol = protocol_from_dict(value)
        print "PROTOCOL RETRIEVED FROM DICT:::"
        print protocol
        app.protocol_controller.modified = True
        emit_signal("on_protocol_changed")
        app.protocol_controller.activate_protocol(protocol)

    ###########################################################################
    # MicroDrop pyutilib plugin handlers
    # ==================================
    def on_exit(self):
        # TODO: FIX ME (This needs to be triggered by microdrop on exit)
        self.mqtt_client.publish("microdrop/microdrop/plugin-exited","{}", retain=True)

    def on_connect(self, client, userdata, flags, rc):
        # self.mqtt_client.subscribe("microdrop/dmf-device-ui/change-protocol-state")
        # self.mqtt_client.subscribe("microdrop/dmf-device-ui/change-repeat")
        # self.mqtt_client.subscribe("microdrop/data-controller/load-protocol")
        # self.mqtt_client.subscribe("microdrop/droplet-planning-plugin/step-complete")
        # self.mqtt_client.subscribe("microdrop/put/mqtt-plugin/state/steps")
        # self.mqtt_client.subscribe("microdrop/put/mqtt-plugin/state/protocol")
        # self.mqtt_client.subscribe("microdrop/put/mqtt-plugin/state/step-number")

        self.mqtt_client.publish("microdrop/microdrop/plugin-started","{}", retain=True)
        atexit.register(self.on_exit)

    def on_message(self, client, userdata, msg):
        '''
        Callback for when a ``PUBLISH`` message is received from the broker.
        '''
        if msg.topic == 'microdrop/dmf-device-ui/change-step':
            self.change_step(json.loads(msg.payload))
        if msg.topic == "microdrop/dmf-device-ui/change-protocol-state":
            self.change_protocol_state(json.loads(msg.payload))
        if msg.topic == "microdrop/dmf-device-ui/change-repeat":
            self.change_protocol_repeat(json.loads(msg.payload))
        if msg.topic == "microdrop/droplet-planning-plugin/step-complete":
            self.step_complete(json.loads(msg.payload))
        if msg.topic == "microdrop/put/mqtt-plugin/state/steps":
            self.steps = json.loads(msg.payload, object_hook=pandas_object_hook)
        if msg.topic == "microdrop/put/mqtt-plugin/state/protocol":
            self.protocol = json.loads(msg.payload, object_hook=pandas_object_hook)
        if msg.topic == "microdrop/put/mqtt-plugin/state/step-number":
            self.step_number = json.loads(msg.payload, object_hook=pandas_object_hook)

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

    def on_protocol_repeats_changed(self):
        # TODO: Make this event triggered by microdrop (or implement)
        #      altertnative in some form of protocol controller plugin
        app = get_app()
        text_entry = app.protocol_controller.textentry_protocol_repeats
        val = text_entry.get_text()
        self.mqtt_client.publish("microdrop/mqtt-plugin/protocol-repeats-changed",val)

    def on_protocol_changed(self):
        app = get_app()

        # TODO: hook in protocol name with webui (should be indexed by default)
        if app.protocol.name is None:
            app.protocol.name = "unnamed"

        self.mqtt_client.publish("microdrop/mqtt-plugin/protocol-changed",
                                 app.protocol.to_json(), retain=True)

    def on_protocol_swapped(self, old_protocol, protocol):
        # if protocol.name is None:
        #     protocol.name = "unnamed"
        # self.mqtt_client.publish("microdrop/mqtt-plugin/protocol-swapped",
        #                          protocol.to_json(), retain=True)
        pass

    def on_step_swapped(self, old_step_number, step_number):
        """
        Called when protocol controller swaps steps
        """
        self.step_changed(step_number, old_step_number)

    def on_step_options_changed(self, plugin, step_number):
        """
        Called when step options (Field values etc.) are updated
        """
        self.step_changed(step_number, step_number)

    def step_changed(self, step_number, old_step_number):
        app = get_app()
        step = app.protocol.steps[step_number]
        data = step.plugin_data

        msg = {}
        msg["stepNumber"] = step_number
        msg["prevStepNumber"] = old_step_number
        msg["stepData"] = data
        msg = json.dumps(msg, cls=PandasJsonEncoder)

        # self.mqtt_client.publish("microdrop/mqtt-plugin/step-changed",
        #                          msg, retain=True)

    def step_complete(self, msg):
        plugin_name = msg.plugin_name
        return_value = msg.return_value
        emit_signal("on_step_complete", [plugin_name, return_value])

    def change_step(self,step_number):
        app = get_app()
        app.protocol.goto_step(step_number)

    def delete_step(self, step_number):
        app = get_app()
        app.protocol.delete_step(step_number)
        num_steps = len(app.protocol.steps)

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

    def change_protocol_repeat(self, val):
        # XXX: Manually updating gtk text entry:
        app = get_app()
        text_entry = app.protocol_controller.textentry_protocol_repeats
        text_entry.set_text(str(val))
        emit_signal("on_protocol_repeats_changed")


PluginGlobals.pop_env()
