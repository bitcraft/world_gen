import os.path

import pygame

from lib.config import RESOURCES_DIR


def load_image(filename):
    return pygame.image.load(os.path.join(RESOURCES_DIR, filename))
