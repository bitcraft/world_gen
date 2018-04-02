""" Quest - An epic journey.
Simple demo that demonstrates PyTMX and pyscroll.
requires pygame and pytmx.
https://github.com/bitcraft/pytmx
pip install pytmx
"""
import os.path

import pygame
from pygame.locals import *

import pyscroll
import pyscroll.data
from pyscroll.group import PyscrollGroup

from lib import perlin

# define configuration variables here
RESOURCES_DIR = 'resources'
HERO_MOVE_SPEED = 200  # pixels per second


# simple wrapper to keep the screen resizeable
def init_screen(width, height):
    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
    return screen


# make loading images a little easier
def load_image(filename):
    return pygame.image.load(os.path.join(RESOURCES_DIR, filename))


class Hero(pygame.sprite.Sprite):
    """ Our Hero
    The Hero has three collision rects, one for the whole sprite "rect" and
    "old_rect", and another to check collisions with walls, called "feet".
    The position list is used because pygame rects are inaccurate for
    positioning sprites; because the values they get are 'rounded down'
    as integers, the sprite would move faster moving left or up.
    Feet is 1/2 as wide as the normal rect, and 8 pixels tall.  This size size
    allows the top of the sprite to overlap walls.  The feet rect is used for
    collisions, while the 'rect' rect is used for drawing.
    There is also an old_rect that is used to reposition the sprite if it
    collides with level walls.
    """

    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        self.image = load_image('hero.png').convert_alpha()
        self.velocity = [0, 0]
        self._position = [0, 0]
        self._old_position = self.position
        self.rect = self.image.get_rect()
        self.feet = pygame.Rect(0, 0, self.rect.width * .5, 8)

    @property
    def position(self):
        return list(self._position)

    @position.setter
    def position(self, value):
        self._position = list(value)

    def update(self, dt):
        self._old_position = self._position[:]
        self._position[0] += self.velocity[0] * dt
        self._position[1] += self.velocity[1] * dt
        self.rect.topleft = self._position
        self.feet.midbottom = self.rect.midbottom

    def move_back(self, dt):
        """ If called after an update, the sprite can move back
        """
        self._position = self._old_position
        self.rect.topleft = self._position
        self.feet.midbottom = self.rect.midbottom


class InfiniteMap(pyscroll.PyscrollDataAdapter):
    """ DataAdapter to allow infinite maps rendered by pyscroll

    Doesn't store map data; tile is chosen deterministically when displayed on screen
    """
    def __init__(self, tile_size=(32, 32)):
        super(InfiniteMap, self).__init__()
        self.base_tiler = perlin.SimplexNoise()
        self.tile_size = tile_size
        self.map_size = 1024, 1024
        self.visible_tile_layers = [1]
        self.all_tiles = list()
        self.tiles = list()
        self.tile_map = (118, 183, 182, 181, 373)  # the tiles used on the map
        self.load_texture()

    def load_texture(self):
        surface = load_image('terrain_atlas.png').convert_alpha()
        tw, th = 32, 32
        sw, sh = surface.get_size()

        append = self.all_tiles.append
        subsurface = surface.subsurface
        for y in range(0, sh, th):
            for x in range(0, sw, tw):
                append(subsurface((x, y, tw, th)))

        for i in self.tile_map:
            self.tiles.append(self.all_tiles[i])

    def get_tile_image(self, x, y, l):
        """ Get a tile for the x, y position

        Uses simplex noise to determine what tile to use

        :param x:
        :param y:
        :param l:
        :return:
        """
        noise = self.base_tiler.noise2
        base_value = ((noise(x / 32, y / 32) + 1) / 2) * 4
        base_value = pow(base_value, .9)
        grass_value = ((noise(x, y) + 1) / 2) * 4
        final_value = (base_value * .7) + (grass_value * .3)
        tile_id = int(round(final_value))
        return self.tiles[tile_id]


class QuestGame(object):
    """ This class is a basic game.
    This class will load resources, create a pyscroll group, a hero object.
    It also reads input and moves the Hero around the map.
    Finally, it uses a pyscroll group to render the map and Hero.
    """

    def __init__(self):

        # true while running
        self.running = False

        # create new data source for pyscroll
        map_data = InfiniteMap()

        # create new renderer (camera)
        self.map_layer = pyscroll.BufferedRenderer(map_data, screen.get_size(), clamp_camera=True, tall_sprites=1)
        self.map_layer.zoom = 1

        # pyscroll supports layered rendering.  our map has 3 'under' layers
        # layers begin with 0, so the layers are 0, 1, and 2.
        # since we want the sprite to be on top of layer 1, we set the default
        # layer for sprites as 2
        self.group = PyscrollGroup(map_layer=self.map_layer, default_layer=2)
        self.hero = Hero()
        self.hero.position = self.map_layer.map_rect.center

        # add our hero to the group
        self.group.add(self.hero)

    def draw(self, surface):

        # center the map/screen on our Hero
        self.group.center(self.hero.rect.center)

        # draw the map and all sprites
        self.group.draw(surface)

    def handle_input(self):
        """ Handle pygame input events
        """
        poll = pygame.event.poll

        event = poll()
        while event:
            if event.type == QUIT:
                self.running = False
                break

            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    self.running = False
                    break

                elif event.key == K_EQUALS:
                    self.map_layer.zoom += .25

                elif event.key == K_MINUS:
                    value = self.map_layer.zoom - .25
                    if value > 0:
                        self.map_layer.zoom = value

            # this will be handled if the window is resized
            elif event.type == VIDEORESIZE:
                init_screen(event.w, event.h)
                self.map_layer.set_size((event.w, event.h))

            event = poll()

        # using get_pressed is slightly less accurate than testing for events
        # but is much easier to use.
        pressed = pygame.key.get_pressed()
        if pressed[K_UP]:
            self.hero.velocity[1] = -HERO_MOVE_SPEED
        elif pressed[K_DOWN]:
            self.hero.velocity[1] = HERO_MOVE_SPEED
        else:
            self.hero.velocity[1] = 0

        if pressed[K_LEFT]:
            self.hero.velocity[0] = -HERO_MOVE_SPEED
        elif pressed[K_RIGHT]:
            self.hero.velocity[0] = HERO_MOVE_SPEED
        else:
            self.hero.velocity[0] = 0

    def update(self, dt):
        """ Tasks that occur over time should be handled here
        """
        self.group.update(dt)

    def run(self):
        """ Run the game loop
        """
        clock = pygame.time.Clock()
        self.running = True

        from collections import deque
        times = deque(maxlen=30)

        try:
            while self.running:
                dt = clock.tick(120) / 1000.
                times.append(clock.get_fps())

                self.handle_input()
                self.update(dt)
                self.draw(screen)
                pygame.display.flip()

        except KeyboardInterrupt:
            self.running = False


if __name__ == "__main__":
    pygame.init()
    pygame.font.init()
    screen = init_screen(800, 600)
    pygame.display.set_caption('Quest - An epic journey.')

    try:
        game = QuestGame()
        game.run()
    except:
        pygame.quit()
        raise
