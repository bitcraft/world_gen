from itertools import product
from array import array

import pygame
import pyscroll

from lib import perlin
from lib.resources import load_image
import lib.rules as lib_rules

DEBUG_CODES = 0

NOISE_SIZE = 32

GRASS = 1
LDIRT = 2
WATER = 4
WALL = 8

POWERS9 = [1, 2, 4, 8, 16, 32, 64, 128, 256]
POWERS3 = [64, 128, 256]


def get_grass_value(x, y, noise):
    grass_value = ((noise(x / NOISE_SIZE, y / NOISE_SIZE) + 1) / 2) * 4
    variation = ((noise(x, y) + 1) / 2) * 4
    return (grass_value * .7) + (variation * .3)


class InfiniteMap(pyscroll.PyscrollDataAdapter):
    """ DataAdapter to allow infinite maps rendered by pyscroll

    Automatically checks biome boundaries and chooses the best tile
    """

    def __init__(self, tile_size=(32, 32)):
        super(InfiniteMap, self).__init__()
        self.base_tiler = perlin.SimplexNoise()

        # required for pyscroll
        self._old_view = None
        self.tile_size = tile_size
        self.map_size = 1024, 1024
        self.visible_tile_layers = [0]

        self.last_value = 0
        self.last_x = None
        self.last_y = None
        self.scan_x = 0
        self.total_checks = 0
        self.cached_checks = 0

        self.seen_tiles = set()
        self.biome_map = [array('B', [0] * 1024) for i in range(1024)]
        self.tile_map = [array('H', [0] * 1024) for i in range(1024)]

        self.font = None

        self.tilesets = {
            'ldirt-empty': (112, 49, 48, 80, 17, 111, None, 79, 16, None, 113, 81, 144, 143, 145, 47),
            'sand-empty': (385, 322, 321, 353, 290, 384, None, 352, 289, None, 386, 354, 417, 416, 418, 320),
            'water-grass': (391, 328, 327, 359, 296, 390, None, 358, 295, None, 392, 360, 423, 422, 424, 326),
            'grass': (118, 183, 182, 181, 374),
            'wall': (38, None, None, 6, 0, 0, 0, 5, 0, 0, 0, 7, 0, 0, 0, 0),
        }
        self.all_tiles = list()

        self.load_texture()

    def score3(self, x, y, secondary):
        # top, center, bottom tiles
        tiles = [self.biome_map[y][x] for x, y in ((x, y - 1), (x, y), (x, y + 1))]
        return sum(i for v, i in zip(tiles, POWERS3) if v == secondary)

    def score9(self, x, y, secondary):
        # all surrounding tiles, plus center
        # unroll loop?
        tiles = [self.biome_map[y][x] for x, y in ((x - 1, y - 1), (x - 1, y), (x - 1, y + 1), (x, y - 1), (x, y),
                                                   (x, y + 1), (x + 1, y - 1), (x + 1, y), (x + 1, y + 1))]
        return sum(i for v, i in zip(tiles, POWERS9) if v == secondary)

    def reload(self):
        import importlib
        try:
            importlib.reload(lib_rules)
        except AttributeError:
            pass

        self.load_texture()

    def load_texture(self):
        self.font = pygame.font.Font(None, 18)

        surface = load_image('terrain_atlas.png').convert_alpha()
        tw, th = 32, 32
        sw, sh = surface.get_size()

        self.all_tiles = list()
        append = self.all_tiles.append
        subsurface = surface.subsurface
        for y, x in product(range(0, sh, th), range(0, sw, tw)):
            append(subsurface((x, y, tw, th)))

    def edge_tile(self, x, y, l, primary, secondary, palette):
        # determine if the previous score can be reused:
        # * must be same y as last check
        # * x must be exactly x+1 as last check
        # if it cannot be reused, then start check using all surrounding tiles
        if self.last_y == y:
            if self.last_x + 1 != x:
                self.last_value = 0
                self.scan_x = x
        else:
            self.last_value = 0
            self.last_y = y
            self.scan_x = x

        self.last_x = x

        self.total_checks += 1
        if x - self.scan_x == 0:

            # this is a new segment, so scan all tiles
            self.last_value = self.score9(x, y, secondary)

        else:
            # able to reuse some of the old score
            self.cached_checks += 1

            # move left
            self.last_value >>= 3
            self.last_value += self.score3(x + 1, y, secondary)

        # get the tile type based on the score
        tile_type = lib_rules.standard8.get(self.last_value, 0)

        # get the specific tile image for this cell
        tile_id = palette[tile_type]

        # make new image with the score drawn on it
        if DEBUG_CODES:
            tile = self.all_tiles[tile_id].copy()
            text = self.font.render(str(self.last_value), 0, (0, 0, 0))
            tile.blit(text, (0, 0))
            tile_id = len(self.all_tiles)
            self.all_tiles.append(tile)

        # set the tile
        self.tile_map[y][x] = tile_id

    def get_tile_value(self, x, y, l):
        noise = self.base_tiler.noise2
        streams = ((noise(x / NOISE_SIZE, y / NOISE_SIZE) + 1) / 2)
        grass_value = get_grass_value(x, y, noise)

        # elevation = round(((noise(x / 46, y / 32) + 1) / 2) * 4) / 4
        elevation = 0

        if elevation > .999999:
            self.biome_map[y][x] = WALL

        elif streams >= .80:
            self.biome_map[y][x] = WATER

        elif grass_value <= .25:
            self.biome_map[y][x] = LDIRT

        else:
            self.biome_map[y][x] = GRASS
            self.tile_map[y][x] = self.tilesets['grass'][int(round(grass_value))]

    def prepare_tiles(self, view):
        if not view == self._old_view:
            self._old_view = view.copy()
            x, y, w, h = view
            for yy, xx in product(range(y - 1, y + h + 1), range(x - 1, x + w + 1)):
                if (xx, yy) not in self.seen_tiles:
                    self.seen_tiles.add((xx, yy))
                    self.get_tile_value(xx, yy, 0)

    def set_biome(self, x, y):
        biome = self.biome_map[y][x]

        if biome == WATER:
            palette = self.tilesets['water-grass']
            self.edge_tile(x, y, 0, WATER, GRASS, palette)

        elif biome == LDIRT:
            palette = self.tilesets['ldirt-empty']
            self.edge_tile(x, y, 0, LDIRT, GRASS, palette)

    def get_tile_image(self, x, y, l):
        """ Get a tile for the x, y position

        Uses simplex noise to determine what tile to use

        :param x:
        :param y:
        :param l:
        :return:
        """
        self.set_biome(x, y)
        return self.all_tiles[self.tile_map[y][x]]
