from heapq import heappop, heappush
from itertools import product

import pygame
import pyscroll

from lib import perlin
from lib.resources import load_image
from lib.rules import standard8

DEBUG_CODES = 0


def get_grass_value(x, y, noise):
    grass_value = ((noise(x / 32, y / 32) + 1) / 2) * 4
    variation = ((noise(x, y) + 1) / 2) * 4
    return (grass_value * .7) + (variation * .3)


class InfiniteMap(pyscroll.PyscrollDataAdapter):
    """ DataAdapter to allow infinite maps rendered by pyscroll

    Doesn't store map data; tile is chosen deterministically when displayed on screen
    """

    def __init__(self, tile_size=(32, 32)):
        super(InfiniteMap, self).__init__()
        self.grass_water_dict = dict()
        self.base_tiler = perlin.SimplexNoise()

        # required for pyscroll
        self._old_view = None
        self.tile_size = tile_size
        self.map_size = 1024, 1024
        self.visible_tile_layers = [1]

        self.font = None
        self._first_draw = True

        self.tilesets = {
            'ldirt-empty': (112, 49, 48, 80, 17, 111, None, 79, 16, None, 113, 81, 144, 143, 145, 47),
            'sand-empty': (385, 322, 321, 353, 290, 384, None, 352, 289, None, 386, 354, 417, 416, 418, 320),
            'water-grass': (391, 328, 327, 359, 296, 390, None, 358, 295, None, 392, 360, 423, 422, 424, 326),
            'grass': (118, 183, 182, 181),
            'wall': (38, None, None, 6, 0, 0, 0, 5, 0, 0, 0, 7, 0, 0, 0, 0),
        }

        self.all_tiles = list()

        self.value_map = dict()
        self.biome_map = dict()
        self.tile_map = dict()
        self.elevation_map = dict()

        self.load_texture()

    def fill(self, start, bounds, blacklist=set()):
        def cell_available(cell):
            return coord_available(cell)

        def coord_available(coord):
            return coord not in closed_set and coord not in blacklist

        bx1, by1, bx2, by2 = bounds

        open_heap = list()
        open_set = set()
        closed_set = set()

        closed_set.add(None)

        open_set.add(start)
        open_heap.append(start)

        path = list()

        while open_set:
            current = heappop(open_heap)

            open_set.remove(current)
            closed_set.add(current)
            path.append(current)

            cells = self.neighbors(*current)

            for cell in cells:
                if cell in closed_set:
                    continue

                if (bx1 <= cell[0] < bx2) and (by1 <= cell[1] < by2):
                    if cell not in open_set:
                        open_set.add(cell)
                        heappush(open_heap, cell)

        for cell in path:
            self.get_tile_value(*cell, 0)

        return None, True

    def neighbors(self, x, y):
        return ((x - 1, y - 1), (x, y - 1), (x + 1, y - 1), (x + 1, y),
                (x + 1, y + 1), (x, y + 1), (x - 1, y + 1), (x - 1, y))

    def surrounding8(self, x, y):
        return [self.biome_map.get(i, None) for i in
                ((x - 1, y - 1), (x, y - 1), (x + 1, y - 1), (x + 1, y),
                 (x + 1, y + 1), (x, y + 1), (x - 1, y + 1), (x - 1, y))]

    def surrounding4(self, x, y):
        return [self.biome_map.get(i, None) for i in
                ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y))]

    def load_texture(self):
        self.font = pygame.font.Font(None, 18)

        surface = load_image('terrain_atlas.png').convert_alpha()
        tw, th = 32, 32
        sw, sh = surface.get_size()

        append = self.all_tiles.append
        subsurface = surface.subsurface
        for y, x in product(range(0, sh, th), range(0, sw, tw)):
            append(subsurface((x, y, tw, th)))

    def edge_tile(self, x, y, l, primary, secondary, palette):

        score = 0
        for i, v in enumerate(self.surrounding8(x, y)):
            if v is None:
                pass

            elif v == primary:
                # score += pow(2, i + 4)
                pass

            elif v == secondary:
                score += pow(2, i)

        # tile_type = standard4.get(score, 0)
        tile_type = standard8.get(score, 0)
        tile_id = palette[tile_type]

        if DEBUG_CODES:
            tile = self.all_tiles[tile_id].copy()
            text = self.font.render(str(score), 0, (0, 0, 0))
            tile.blit(text, (0, 0))
            tile_id = len(self.all_tiles)
            self.all_tiles.append(tile)

        self.tile_map[(x, y)] = tile_id

    def get_tile_value(self, x, y, l):
        noise = self.base_tiler.noise2

        streams = ((noise(x / 32, y / 32) + 1) / 2)
        grass_value = get_grass_value(x, y, noise)

        noise = self.base_tiler.noise2
        elevation = ((noise(x / 2048, y / 1024) + 1) / 2)

        if elevation > .999999:
            self.biome_map[(x, y)] = 'wall'
            self.value_map[(x, y)] = 1
            self.tile_map[(x, y)] = 0

        elif streams > .75:
            self.biome_map[(x, y)] = 'water'
            self.value_map[(x, y)] = 1
            self.tile_map[(x, y)] = 0

        else:
            self.biome_map[(x, y)] = 'grass'
            self.value_map[(x, y)] = grass_value
            self.tile_map[(x, y)] = self.tilesets['grass'][int(round(grass_value))]

    def prepare_tiles(self, view):
        if not view == self._old_view:
            self._old_view = view.copy()
            x, y, w, h = view
            for yy, xx in product(range(y - 1, y + h + 1), range(x - 1, x + w + 1)):
                self.get_tile_value(xx, yy, 0)

    def get_tile_image(self, x, y, l):
        """ Get a tile for the x, y position

        Uses simplex noise to determine what tile to use

        :param x:
        :param y:
        :param l:
        :return:
        """
        # if self._first_draw:
        #     self._first_draw = False
        #     bounds = x, y, x + 60, y + 60
        #     self.fill((x, y), bounds)
        biome = self.biome_map[(x, y)]

        if biome == 'water':
            palette = self.tilesets['water-grass']
            self.edge_tile(x, y, l, 'water', 'grass', palette)

        tile_id = self.tile_map.get((x, y), None)
        return self.all_tiles[tile_id] if tile_id else None
