import logging
import socket

from microdrop.plugin_helpers import get_plugin_info
from microdrop.plugin_manager import (PluginGlobals, Plugin, IPlugin,
                                      implements)
import paho.mqtt.client as mqtt
import path_helpers as ph

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

logger = logging.getLogger(__name__)


PluginGlobals.push_env('microdrop.managed')

class MqttPlugin(Plugin):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    version = __version__
    plugin_name = get_plugin_info(ph.path(__file__).parent).plugin_name

    def __init__(self):
        self.name = self.plugin_name
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_disconnect = self.on_disconnect
        self.mqtt_client.on_message = self.on_connect

    def _connect(self):
        try:
            # Connect to MQTT broker.
            # TODO: Make connection parameters configurable.
            self.mqtt_client.connect(host='localhost', port=1883, keepalive=60)
        except socket.error:
            logger.error('Error connecting to MQTT broker.')

    ###########################################################################
    # MQTT client handlers
    # ====================
    def on_connect(self, client, userdata, flags, rc):
        '''
        Callback for when the client receives a ``CONNACK`` response from the
        broker.

        Parameters
        ----------
        client : paho.mqtt.client.Client
            The client instance for this callback.
        userdata : object
            The private user data as set in :class:`paho.mqtt.client.Client`
            constructor or :func:`paho.mqtt.client.Client.userdata_set`.
        flags : dict
            Response flags sent by the broker.

            The flag ``flags['session present']`` is useful for clients that
            are using clean session set to 0 only.

            If a client with clean session=0, that reconnects to a broker that
            it has previously connected to, this flag indicates whether the
            broker still has the session information for the client.

            If 1, the session still exists.
        rc : int
            The connection result.

            The value of rc indicates success or not:

              - 0: Connection successful
              - 1: Connection refused - incorrect protocol version
              - 2: Connection refused - invalid client identifier
              - 3: Connection refused - server unavailable
              - 4: Connection refused - bad username or password
              - 5: Connection refused - not authorised
              - 6-255: Currently unused.

        Notes
        -----

        Subscriptions should be defined in this method to ensure subscriptions
        will be renewed upon reconnecting after a loss of connection.
        '''
        logger.info('Connected to MQTT broker with result code:', rc)
        import pdb; pdb.set_trace()

    def on_disconnect(self, *args, **kwargs):
        # Try to reconnect
        self.mqtt_client.loop_stop()
        self._connect()
        self.mqtt_client.loop_start()

    def on_message(self, client, userdata, msg):
        '''
        Callback for when a ``PUBLISH`` message is received from the broker.
        '''
        logger.info('[on_message] %s: "%s"', msg.topic, msg.payload)
        # import pdb; pdb.set_trace()

    ###########################################################################
    # MicroDrop pyutilib plugin handlers
    # ==================================
    def on_plugin_disable(self):
        """
        Handler called once the plugin instance is disabled.
        """
        # Stop client loop (if running).
        self.mqtt_client.loop_stop()

    def on_plugin_enable(self):
        """
        Handler called once the plugin instance is enabled.
        """
        # super(MqttPlugin, self).on_plugin_enable()

        # Connect to MQTT broker.
        self._connect()


PluginGlobals.pop_env()
