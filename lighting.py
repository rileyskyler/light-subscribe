import appdaemon.plugins.hass.hassapi as hass
import yaml
import time


def get_scenes():
    with open(r'/config/appdaemon/apps/lighting/configuration/scenes_.yaml') as file:
        scenes = yaml.load(file, Loader=yaml.FullLoader)
        return scenes


def get_triggers():
    with open(r'/config/appdaemon/apps/lighting/configuration/triggers.yaml') as file:
        triggers = yaml.load(file, Loader=yaml.FullLoader)
        return triggers


def get_lights():
    with open(r'/config/appdaemon/apps/lighting/configuration/lights.yaml') as file:
        lights = yaml.load(file, Loader=yaml.FullLoader)
        return lights


def get_exhibitions():
    with open(r'/config/appdaemon/apps/lighting/configuration/exhibitions.yaml') as file:
        exhibitions = yaml.load(file, Loader=yaml.FullLoader)
        return exhibitions


class Scene:

    def __init__(self, lighting, config):
        self.id = config['id']
        self.color = config['color']
        self.expiration = None
        if('expiration' in config):
            self.expiration = config['expiration']


class Light:

    def __init__(self, lighting, state, config):
        self.lighting = lighting
        self.id = config['entity_id']
        self.power = state['state']
        self.exhibitions = []

    def register_exhibitions(self, exhibitions):
        self.exhibitions = exhibitions
        self.update()

    def update(self):
        matched_exhibition = False
        for idx, exhibition in self.exhibitions:
            if(exhibition.active):
                if(exhibition.cluster):
                    matched_exhibition = True
                    return self.id
                else:
                    self.render(exhibition)
                    matched_exhibition = True
            break
        if(not matched_exhibition):
            self.render(None)

    def render(self, exhibition):
        if(exhibition and (self.power == 'on' or exhibition.interrupt)):
            return self.lighting.render(
                "light/turn_on",
                entity_id=[self.id],
                color_name=exhibition.scene.color,
                transition=0
            )
        elif(self.power == 'on'):
            return self.lighting.render(
                "light/turn_off",
                entity_id=self.id
            )


class Exhibition:

    def __init__(self, lighting, scene, config):
        self.id = config['id']
        self.scene = scene
        self.lights = []
        self.cluster = True
        self.lighting = lighting

        if('activated' in config):
            self.active = config['activated']
        else:
            self.active = False

    def register_light(self, light):
        self.lights.append(light)

    def activate(self):
        self.active = True
        light_ids = []
        for light in self.lights:
            id = light.update(self)
            if(id):
                light_ids.append(id)
        if(light_ids):
            self.render(light_ids)
        if(self.scene.expiration):
            time.sleep(self.scene.expiration)
            self.deactivate()

    def deactivate(self):
        self.active = False
        for light in self.lights:
            light.render()

    def render(self, light_ids):
        return self.lighting.render(
            "light/turn_on",
            entity_id=lights,
            color_name=exhibition.scene.color,
            transition=0
        )


class Trigger:

    def __init__(self, lighting, config):
        self.lighting = lighting
        self.id = config['id']
        self.lighting = lighting
        self.exhibitions = []
        self.trigger_states = {
            'activate': config['activate']
        }
        self.handle = lighting.listen_state(
            self.handle_state_change, config['entity_id'])

    def register_exhibition(self, exhibition):
        self.exhibitions.append(exhibition)

    def handle_state_change(self, entity, attribute, old, new, kwargs):
        if(new == self.trigger_states['activate']):
            self.activate()
        # elif(new == self.trigger_states['deactivate']):
        #     self.deactivate()

    def activate(self):
        for exhibition in self.exhibitions:
            exhibition.activate()

    def deactivate(self):
        for exhibition in self.exhibitions:
            exhibition.deactivate()


class Lighting(hass.Hass):

    def initialize(self):
        self.scenes = {}
        self.exhibitions = {}
        self.triggers = {}
        self.lights = {}

        scenes_config = get_scenes()
        for scene_config in scenes_config:
            scene = Scene(self, scene_config)
            self.scenes[scene_config['id']] = scene

        exhibitions_config = get_exhibitions()
        for exhibition_config in exhibitions_config:
            exhibition = Exhibition(
                self,
                self.scenes[exhibition_config['scene']],
                exhibition_config
            )
            self.exhibitions[exhibition_config['id']] = exhibition

        triggers_config = get_triggers()
        for trigger_config in triggers_config:
            trigger = Trigger(self, trigger_config)
            if 'exhibitions' in trigger_config:
                for exhibition_id in trigger_config['exhibitions']:
                    trigger.register_exhibition(
                        self.exhibitions[exhibition_id])
            self.triggers[trigger_config['id']] = trigger

        lights_config = get_lights()
        for light_config in lights_config:
            entity_id = light_config['entity_id']
            light_state = self.get_state(entity_id, attribute="all")
            light = Light(self, light_state, light_config)
            light_exhibitions = []
            for exhibition_id in light_config['exhibitions']:
                exhibition = self.exhibitions[exhibition_id]
                exhibition.register_light(light)
                light_exhibitions.append(exhibition)
            light.register_exhibitions(light_exhibitions)
            self.lights[entity_id] = light
