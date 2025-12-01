import pygame
import numpy as np
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional
import random

# Константы
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FOV = math.pi / 3  # 60 градусов
HALF_FOV = FOV / 2
NUM_RAYS = 320
MAX_DEPTH = 20
DELTA_ANGLE = FOV / NUM_RAYS
SCALE = SCREEN_WIDTH // NUM_RAYS
HALF_HEIGHT = SCREEN_HEIGHT // 2

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
DARK_GRAY = (50, 50, 50)
LIGHT_GRAY = (100, 100, 100)
BROWN = (139, 69, 19)
DARK_RED = (139, 0, 0)
CEILING_COLOR = (50, 50, 50)
FLOOR_COLOR = (80, 80, 80)


@dataclass
class Vector2:
    x: float
    y: float

    def __add__(self, other):
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return Vector2(self.x * scalar, self.y * scalar)

    def length(self):
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def normalize(self):
        l = self.length()
        if l > 0:
            return Vector2(self.x / l, self.y / l)
        return Vector2(0, 0)

    def distance_to(self, other):
        return (self - other).length()


class Weapon:
    def __init__(self):
        self.damage = 25
        self.fire_rate = 0.3  # секунд между выстрелами
        self.last_shot = 0
        self.ammo = 50
        self.max_ammo = 100
        self.is_firing = False
        self.fire_animation_time = 0
        self.fire_animation_duration = 0.1

    def can_fire(self, current_time):
        return current_time - self.last_shot >= self.fire_rate and self.ammo > 0

    def fire(self, current_time):
        if self.can_fire(current_time):
            self.ammo -= 1
            self.last_shot = current_time
            self.is_firing = True
            self.fire_animation_time = current_time
            return True
        return False

    def update(self, current_time):
        if self.is_firing and current_time - self.fire_animation_time > self.fire_animation_duration:
            self.is_firing = False


class Enemy:
    def __init__(self, x: float, y: float, enemy_type: str = "demon"):
        self.pos = Vector2(x, y)
        self.health = 100
        self.max_health = 100
        self.speed = 1.5
        self.damage = 10
        self.attack_range = 1.0
        self.attack_cooldown = 1.0
        self.last_attack = 0
        self.is_alive = True
        self.enemy_type = enemy_type
        self.size = 0.4
        self.animation_frame = 0
        self.last_animation_time = 0

        # Настройки по типу врага
        if enemy_type == "demon":
            self.health = 100
            self.max_health = 100
            self.speed = 1.5
            self.damage = 15
            self.color = RED
        elif enemy_type == "imp":
            self.health = 60
            self.max_health = 60
            self.speed = 2.0
            self.damage = 10
            self.color = BROWN
        elif enemy_type == "baron":
            self.health = 200
            self.max_health = 200
            self.speed = 1.0
            self.damage = 30
            self.color = DARK_RED
            self.size = 0.6

    def take_damage(self, damage: int):
        self.health -= damage
        if self.health <= 0:
            self.is_alive = False
            return True  # Враг убит
        return False

    def update(self, player_pos: Vector2, walls: List, delta_time: float, current_time: float):
        if not self.is_alive:
            return

        # Движение к игроку
        direction = player_pos - self.pos
        distance = direction.length()

        if distance > self.attack_range:
            direction = direction.normalize()
            new_pos = self.pos + direction * (self.speed * delta_time)

            # Проверка коллизий со стенами
            if not self.check_wall_collision(new_pos, walls):
                self.pos = new_pos

        # Анимация
        if current_time - self.last_animation_time > 0.2:
            self.animation_frame = (self.animation_frame + 1) % 4
            self.last_animation_time = current_time

    def check_wall_collision(self, new_pos: Vector2, walls: List) -> bool:
        map_x = int(new_pos.x)
        map_y = int(new_pos.y)

        if 0 <= map_x < len(walls[0]) and 0 <= map_y < len(walls):
            if walls[map_y][map_x] > 0:
                return True
        return False

    def can_attack(self, player_pos: Vector2, current_time: float) -> bool:
        if not self.is_alive:
            return False
        distance = self.pos.distance_to(player_pos)
        return distance <= self.attack_range and current_time - self.last_attack >= self.attack_cooldown

    def attack(self, current_time: float) -> int:
        self.last_attack = current_time
        return self.damage


class Pickup:
    def __init__(self, x: float, y: float, pickup_type: str):
        self.pos = Vector2(x, y)
        self.pickup_type = pickup_type
        self.is_active = True
        self.size = 0.3

        if pickup_type == "health":
            self.value = 25
            self.color = GREEN
        elif pickup_type == "ammo":
            self.value = 20
            self.color = YELLOW
        elif pickup_type == "armor":
            self.value = 50
            self.color = BLUE


class Player:
    def __init__(self, x: float, y: float):
        self.pos = Vector2(x, y)
        self.angle = 0
        self.health = 100
        self.max_health = 100
        self.armor = 0
        self.max_armor = 100
        self.speed = 3.0
        self.rotation_speed = 2.5
        self.weapon = Weapon()
        self.score = 0
        self.kills = 0

    def move(self, forward: float, strafe: float, walls: List, delta_time: float):
        # Вычисляем направление движения
        move_x = math.cos(self.angle) * forward - math.sin(self.angle) * strafe
        move_y = math.sin(self.angle) * forward + math.cos(self.angle) * strafe

        # Нормализуем если двигаемся по диагонали
        if forward != 0 and strafe != 0:
            move_x *= 0.707
            move_y *= 0.707

        # Применяем скорость
        new_x = self.pos.x + move_x * self.speed * delta_time
        new_y = self.pos.y + move_y * self.speed * delta_time

        # Проверка коллизий
        margin = 0.2

        # Проверяем X
        if not self.check_collision(new_x, self.pos.y, walls, margin):
            self.pos.x = new_x

        # Проверяем Y
        if not self.check_collision(self.pos.x, new_y, walls, margin):
            self.pos.y = new_y

    def check_collision(self, x: float, y: float, walls: List, margin: float) -> bool:
        # Проверяем 4 угла вокруг игрока
        for dx in [-margin, margin]:
            for dy in [-margin, margin]:
                check_x = int(x + dx)
                check_y = int(y + dy)
                if 0 <= check_x < len(walls[0]) and 0 <= check_y < len(walls):
                    if walls[check_y][check_x] > 0:
                        return True
        return False

    def rotate(self, angle_delta: float, delta_time: float):
        self.angle += angle_delta * self.rotation_speed * delta_time
        # Нормализуем угол
        self.angle = self.angle % (2 * math.pi)

    def take_damage(self, damage: int):
        # Сначала поглощаем урон бронёй
        if self.armor > 0:
            armor_absorbed = min(self.armor, damage // 2)
            self.armor -= armor_absorbed
            damage -= armor_absorbed

        self.health -= damage
        if self.health < 0:
            self.health = 0
        return self.health <= 0

    def heal(self, amount: int):
        self.health = min(self.health + amount, self.max_health)

    def add_armor(self, amount: int):
        self.armor = min(self.armor + amount, self.max_armor)

    def add_ammo(self, amount: int):
        self.weapon.ammo = min(self.weapon.ammo + amount, self.weapon.max_ammo)


class DoomGame:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("DOOM - Python Edition")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.big_font = pygame.font.Font(None, 72)

        # Игровое состояние
        self.game_state = "menu"  # menu, playing, paused, game_over, victory
        self.current_level = 1
        self.max_level = 3

        # Инициализация уровня
        self.load_level(self.current_level)

        # Создаём текстуры стен
        self.wall_textures = self.create_wall_textures()

        # Звуки
        self.sounds = {}
        self.create_sounds()

    def create_sounds(self):
        """Создаём простые звуки программно"""
        # В реальной игре здесь загружались бы звуковые файлы
        pass

    def create_wall_textures(self) -> dict:
        """Создаём простые текстуры стен"""
        textures = {}
        texture_size = 64

        # Текстура 1 - Кирпичи
        tex1 = pygame.Surface((texture_size, texture_size))
        tex1.fill((100, 50, 50))
        for y in range(0, texture_size, 16):
            for x in range(0, texture_size, 32):
                offset = 16 if (y // 16) % 2 else 0
                pygame.draw.rect(tex1, (80, 40, 40), (x + offset, y, 30, 14))
                pygame.draw.rect(tex1, (60, 30, 30), (x + offset, y, 30, 14), 1)
        textures[1] = tex1

        # Текстура 2 - Металл
        tex2 = pygame.Surface((texture_size, texture_size))
        tex2.fill((70, 70, 80))
        for i in range(0, texture_size, 8):
            pygame.draw.line(tex2, (50, 50, 60), (0, i), (texture_size, i))
            pygame.draw.line(tex2, (90, 90, 100), (0, i + 1), (texture_size, i + 1))
        textures[2] = tex2

        # Текстура 3 - Камень
        tex3 = pygame.Surface((texture_size, texture_size))
        tex3.fill((80, 80, 70))
        for _ in range(50):
            x, y = random.randint(0, texture_size - 4), random.randint(0, texture_size - 4)
            color = random.randint(60, 100)
            pygame.draw.rect(tex3, (color, color, color - 10), (x, y, 4, 4))
        textures[3] = tex3

        return textures

    def load_level(self, level_num: int):
        """Загружаем уровень"""
        self.walls = self.get_level_map(level_num)
        self.player = Player(1.5, 1.5)
        self.enemies = []
        self.pickups = []
        self.doors = []

        # Размещаем врагов и предметы
        self.spawn_entities(level_num)

    def get_level_map(self, level_num: int) -> List[List[int]]:
        """Возвращает карту уровня"""
        if level_num == 1:
            return [
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 2, 2, 2, 0, 0, 0, 0, 3, 3, 3, 0, 0, 1],
                [1, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 1],
                [1, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 1],
                [1, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 1],
                [1, 0, 0, 3, 3, 3, 0, 0, 0, 0, 2, 2, 2, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            ]
        elif level_num == 2:
            return [
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 1, 0, 0, 2, 2, 2, 2, 0, 0, 1, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 1, 1, 0, 0, 0, 0, 0, 2, 0, 0, 2, 0, 0, 0, 0, 0, 1, 1, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 0, 0, 1],
                [1, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 1],
                [1, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1],
                [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            ]
        else:  # level 3
            return [
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 0, 0, 1],
                [1, 0, 2, 0, 0, 0, 0, 3, 3, 3, 0, 0, 0, 0, 3, 3, 3, 0, 0, 0, 2, 0, 0, 1],
                [1, 0, 2, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 2, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 2, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 2, 0, 0, 1],
                [1, 0, 2, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 2, 0, 0, 1],
                [1, 0, 2, 2, 2, 0, 0, 3, 3, 3, 0, 0, 0, 0, 3, 3, 3, 0, 2, 2, 2, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            ]

    def spawn_entities(self, level_num: int):
        """Размещаем врагов и предметы на уровне"""
        if level_num == 1:
            # Враги
            self.enemies = [
                Enemy(5.5, 5.5, "imp"),
                Enemy(10.5, 5.5, "imp"),
                Enemy(7.5, 10.5, "demon"),
                Enemy(12.5, 12.5, "imp"),
            ]
            # Предметы
            self.pickups = [
                Pickup(3.5, 8.5, "health"),
                Pickup(12.5, 3.5, "ammo"),
                Pickup(8.5, 13.5, "armor"),
            ]
        elif level_num == 2:
            self.enemies = [
                Enemy(5.5, 5.5, "demon"),
                Enemy(14.5, 5.5, "demon"),
                Enemy(10.5, 10.5, "imp"),
                Enemy(5.5, 10.5, "imp"),
                Enemy(14.5, 10.5, "imp"),
                Enemy(10.5, 7.5, "baron"),
            ]
            self.pickups = [
                Pickup(2.5, 2.5, "health"),
                Pickup(17.5, 2.5, "ammo"),
                Pickup(10.5, 14.5, "armor"),
                Pickup(2.5, 13.5, "health"),
                Pickup(17.5, 13.5, "ammo"),
            ]
        else:  # level 3
            self.enemies = [
                Enemy(5.5, 5.5, "baron"),
                Enemy(18.5, 5.5, "baron"),
                Enemy(12.5, 7.5, "demon"),
                Enemy(5.5, 10.5, "demon"),
                Enemy(18.5, 10.5, "demon"),
                Enemy(8.5, 3.5, "imp"),
                Enemy(15.5, 3.5, "imp"),
                Enemy(8.5, 11.5, "imp"),
                Enemy(15.5, 11.5, "imp"),
            ]
            self.pickups = [
                Pickup(2.5, 2.5, "health"),
                Pickup(21.5, 2.5, "health"),
                Pickup(2.5, 11.5, "ammo"),
                Pickup(21.5, 11.5, "ammo"),
                Pickup(12.5, 2.5, "armor"),
            ]

    def cast_ray(self, angle: float) -> Tuple[float, int, float]:
        """Бросаем луч и возвращаем (расстояние, тип стены, позиция текстуры)"""
        sin_a = math.sin(angle)
        cos_a = math.cos(angle)

        # Проверка горизонтальных пересечений
        y_hor, dy = (int(self.player.pos.y) + 1, 1) if sin_a > 0 else (int(self.player.pos.y) - 1e-6, -1)

        depth_hor = MAX_DEPTH
        texture_hor = 0
        x_hor = 0

        if sin_a != 0:
            depth_hor_curr = (y_hor - self.player.pos.y) / sin_a
            x_hor = self.player.pos.x + depth_hor_curr * cos_a

            delta_depth = dy / sin_a
            dx = delta_depth * cos_a

            for _ in range(MAX_DEPTH):
                tile_x = int(x_hor)
                tile_y = int(y_hor)

                if 0 <= tile_x < len(self.walls[0]) and 0 <= tile_y < len(self.walls):
                    if self.walls[tile_y][tile_x] > 0:
                        texture_hor = self.walls[tile_y][tile_x]
                        depth_hor = depth_hor_curr
                        break

                x_hor += dx
                y_hor += dy
                depth_hor_curr += abs(delta_depth)

        # Проверка вертикальных пересечений
        x_vert, dx = (int(self.player.pos.x) + 1, 1) if cos_a > 0 else (int(self.player.pos.x) - 1e-6, -1)

        depth_vert = MAX_DEPTH
        texture_vert = 0
        y_vert = 0

        if cos_a != 0:
            depth_vert_curr = (x_vert - self.player.pos.x) / cos_a
            y_vert = self.player.pos.y + depth_vert_curr * sin_a

            delta_depth = dx / cos_a
            dy = delta_depth * sin_a

            for _ in range(MAX_DEPTH):
                tile_x = int(x_vert)
                tile_y = int(y_vert)

                if 0 <= tile_x < len(self.walls[0]) and 0 <= tile_y < len(self.walls):
                    if self.walls[tile_y][tile_x] > 0:
                        texture_vert = self.walls[tile_y][tile_x]
                        depth_vert = depth_vert_curr
                        break

                x_vert += dx
                y_vert += dy
                depth_vert_curr += abs(delta_depth)

        # Выбираем ближайшее пересечение
        if depth_vert < depth_hor:
            depth = depth_vert
            texture = texture_vert
            y_vert = y_vert % 1
            offset = y_vert if cos_a > 0 else 1 - y_vert
        else:
            depth = depth_hor
            texture = texture_hor
            x_hor = x_hor % 1
            offset = x_hor if sin_a < 0 else 1 - x_hor
            # Немного затемняем горизонтальные стены для глубины
            texture = -texture  # Используем отрицательное значение как маркер

        return depth, texture, offset

    def render_3d(self):
        """Рендерим 3D вид"""
        # Потолок и пол
        pygame.draw.rect(self.screen, CEILING_COLOR, (0, 0, SCREEN_WIDTH, HALF_HEIGHT))
        pygame.draw.rect(self.screen, FLOOR_COLOR, (0, HALF_HEIGHT, SCREEN_WIDTH, HALF_HEIGHT))

        ray_angle = self.player.angle - HALF_FOV
        z_buffer = []

        for ray in range(NUM_RAYS):
            depth, wall_type, offset = self.cast_ray(ray_angle)

            # Убираем эффект рыбьего глаза
            depth *= math.cos(self.player.angle - ray_angle)
            z_buffer.append(depth)

            # Высота стены
            if depth > 0.001:
                wall_height = int(SCREEN_HEIGHT / (depth + 0.0001))
            else:
                wall_height = SCREEN_HEIGHT

            wall_height = min(wall_height, SCREEN_HEIGHT * 2)

            # Позиция стены на экране
            wall_top = HALF_HEIGHT - wall_height // 2

            # Получаем цвет/текстуру
            is_horizontal = wall_type < 0
            wall_type = abs(wall_type)

            if wall_type in self.wall_textures:
                texture = self.wall_textures[wall_type]
                tex_x = int(offset * texture.get_width()) % texture.get_width()

                # Вырезаем столбец текстуры
                column = pygame.Surface((1, texture.get_height()))
                column.blit(texture, (0, 0), (tex_x, 0, 1, texture.get_height()))

                # Масштабируем
                column = pygame.transform.scale(column, (SCALE, wall_height))

                # Затемнение в зависимости от расстояния и ориентации
                darkness = min(255, int(255 / (1 + depth * depth * 0.1)))
                if is_horizontal:
                    darkness = int(darkness * 0.8)

                column.fill((darkness, darkness, darkness), special_flags=pygame.BLEND_MULT)

                self.screen.blit(column, (ray * SCALE, wall_top))
            else:
                # Простой цвет если нет текстуры
                color_val = max(50, min(200, int(200 / (1 + depth * 0.1))))
                if is_horizontal:
                    color_val = int(color_val * 0.8)
                color = (color_val, color_val // 2, color_val // 2)
                pygame.draw.rect(self.screen, color, (ray * SCALE, wall_top, SCALE, wall_height))

            ray_angle += DELTA_ANGLE

        return z_buffer

    def render_sprites(self, z_buffer: List[float]):
        """Рендерим спрайты врагов и предметов"""
        sprites = []

        # Добавляем врагов
        for enemy in self.enemies:
            if enemy.is_alive:
                dx = enemy.pos.x - self.player.pos.x
                dy = enemy.pos.y - self.player.pos.y
                distance = math.sqrt(dx * dx + dy * dy)

                # Угол к врагу
                theta = math.atan2(dy, dx)
                gamma = theta - self.player.angle

                # Нормализация угла
                while gamma > math.pi:
                    gamma -= 2 * math.pi
                while gamma < -math.pi:
                    gamma += 2 * math.pi

                if abs(gamma) < HALF_FOV + 0.5:  # Немного больше FOV для плавности
                    sprites.append({
                        'type': 'enemy',
                        'obj': enemy,
                        'distance': distance,
                        'angle': gamma
                    })

        # Добавляем предметы
        for pickup in self.pickups:
            if pickup.is_active:
                dx = pickup.pos.x - self.player.pos.x
                dy = pickup.pos.y - self.player.pos.y
                distance = math.sqrt(dx * dx + dy * dy)

                theta = math.atan2(dy, dx)
                gamma = theta - self.player.angle

                while gamma > math.pi:
                    gamma -= 2 * math.pi
                while gamma < -math.pi:
                    gamma += 2 * math.pi

                if abs(gamma) < HALF_FOV + 0.5:
                    sprites.append({
                        'type': 'pickup',
                        'obj': pickup,
                        'distance': distance,
                        'angle': gamma
                    })

        # Сортируем по расстоянию (дальние сначала)
        sprites.sort(key=lambda x: x['distance'], reverse=True)

        # Рендерим спрайты
        for sprite_data in sprites:
            distance = sprite_data['distance']
            gamma = sprite_data['angle']

            # Позиция на экране
            screen_x = int((gamma / FOV + 0.5) * SCREEN_WIDTH)

            # Размер спрайта
            sprite_height = int(SCREEN_HEIGHT / (distance + 0.0001))
            sprite_height = min(sprite_height, SCREEN_HEIGHT)

            if sprite_data['type'] == 'enemy':
                enemy = sprite_data['obj']
                sprite_width = int(sprite_height * enemy.size)

                # Проверяем z-buffer
                ray_index = int(screen_x / SCALE)
                if 0 <= ray_index < len(z_buffer):
                    if distance < z_buffer[ray_index]:
                        # Рисуем врага
                        sprite_top = HALF_HEIGHT - sprite_height // 2
                        sprite_left = screen_x - sprite_width // 2

                        # Тело врага
                        body_rect = pygame.Rect(sprite_left, sprite_top, sprite_width, sprite_height)

                        # Затемнение по расстоянию
                        darkness = max(0.3, min(1.0, 1 - distance / MAX_DEPTH))
                        color = tuple(int(c * darkness) for c in enemy.color)

                        pygame.draw.ellipse(self.screen, color, body_rect)

                        # Глаза
                        eye_y = sprite_top + sprite_height // 4
                        eye_size = max(2, sprite_width // 6)
                        pygame.draw.circle(self.screen, (255, 255, 0),
                                           (sprite_left + sprite_width // 3, eye_y), eye_size)
                        pygame.draw.circle(self.screen, (255, 255, 0),
                                           (sprite_left + 2 * sprite_width // 3, eye_y), eye_size)

                        # Индикатор здоровья
                        if enemy.health < enemy.max_health:
                            health_bar_width = sprite_width
                            health_bar_height = 4
                            health_ratio = enemy.health / enemy.max_health

                            pygame.draw.rect(self.screen, RED,
                                             (sprite_left, sprite_top - 8, health_bar_width, health_bar_height))
                            pygame.draw.rect(self.screen, GREEN,
                                             (sprite_left, sprite_top - 8, int(health_bar_width * health_ratio),
                                              health_bar_height))

            elif sprite_data['type'] == 'pickup':
                pickup = sprite_data['obj']
                sprite_width = int(sprite_height * pickup.size * 2)

                ray_index = int(screen_x / SCALE)
                if 0 <= ray_index < len(z_buffer):
                    if distance < z_buffer[ray_index]:
                        sprite_top = HALF_HEIGHT - sprite_height // 4
                        sprite_left = screen_x - sprite_width // 2

                        darkness = max(0.3, min(1.0, 1 - distance / MAX_DEPTH))
                        color = tuple(int(c * darkness) for c in pickup.color)

                        # Рисуем предмет
                        pickup_rect = pygame.Rect(sprite_left, sprite_top,
                                                  sprite_width, sprite_height // 2)
                        pygame.draw.rect(self.screen, color, pickup_rect)
                        pygame.draw.rect(self.screen, WHITE, pickup_rect, 2)

    def render_weapon(self):
        """Рендерим оружие"""
        weapon = self.player.weapon

        # Позиция оружия
        weapon_width = 200
        weapon_height = 200
        weapon_x = SCREEN_WIDTH // 2 - weapon_width // 2
        weapon_y = SCREEN_HEIGHT - weapon_height

        # Смещение при стрельбе
        if weapon.is_firing:
            weapon_y -= 20
            # Вспышка выстрела
            pygame.draw.circle(self.screen, YELLOW,
                               (SCREEN_WIDTH // 2, SCREEN_HEIGHT - weapon_height - 30), 30)
            pygame.draw.circle(self.screen, (255, 200, 0),
                               (SCREEN_WIDTH // 2, SCREEN_HEIGHT - weapon_height - 30), 20)

        # Ствол оружия
        pygame.draw.rect(self.screen, DARK_GRAY,
                         (weapon_x + 70, weapon_y, 60, 150))
        pygame.draw.rect(self.screen, LIGHT_GRAY,
                         (weapon_x + 75, weapon_y, 50, 145))

        # Рукоятка
        pygame.draw.rect(self.screen, BROWN,
                         (weapon_x + 60, weapon_y + 100, 80, 100))
        pygame.draw.rect(self.screen, (100, 50, 0),
                         (weapon_x + 65, weapon_y + 105, 70, 90))

        # Прицел
        crosshair_size = 10
        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2
        pygame.draw.line(self.screen, WHITE,
                         (center_x - crosshair_size, center_y),
                         (center_x + crosshair_size, center_y), 2)
        pygame.draw.line(self.screen, WHITE,
                         (center_x, center_y - crosshair_size),
                         (center_x, center_y + crosshair_size), 2)

    def render_hud(self):
        """Рендерим интерфейс"""
        # Фон HUD
        hud_height = 80
        hud_surface = pygame.Surface((SCREEN_WIDTH, hud_height))
        hud_surface.fill((40, 40, 40))
        hud_surface.set_alpha(200)
        self.screen.blit(hud_surface, (0, SCREEN_HEIGHT - hud_height))

        # Здоровье
        health_text = self.font.render(f"HEALTH: {self.player.health}", True, RED)
        self.screen.blit(health_text, (20, SCREEN_HEIGHT - 70))

        # Полоска здоровья
        pygame.draw.rect(self.screen, (100, 0, 0), (20, SCREEN_HEIGHT - 40, 150, 20))
        health_width = int(150 * (self.player.health / self.player.max_health))
        pygame.draw.rect(self.screen, RED, (20, SCREEN_HEIGHT - 40, health_width, 20))
        pygame.draw.rect(self.screen, WHITE, (20, SCREEN_HEIGHT - 40, 150, 20), 2)

        # Броня
        armor_text = self.font.render(f"ARMOR: {self.player.armor}", True, BLUE)
        self.screen.blit(armor_text, (200, SCREEN_HEIGHT - 70))

        # Полоска брони
        pygame.draw.rect(self.screen, (0, 0, 100), (200, SCREEN_HEIGHT - 40, 150, 20))
        armor_width = int(150 * (self.player.armor / self.player.max_armor))
        pygame.draw.rect(self.screen, BLUE, (200, SCREEN_HEIGHT - 40, armor_width, 20))
        pygame.draw.rect(self.screen, WHITE, (200, SCREEN_HEIGHT - 40, 150, 20), 2)

        # Патроны
        ammo_text = self.font.render(f"AMMO: {self.player.weapon.ammo}/{self.player.weapon.max_ammo}", True, YELLOW)
        self.screen.blit(ammo_text, (400, SCREEN_HEIGHT - 55))

        # Счёт
        score_text = self.font.render(f"SCORE: {self.player.score}", True, WHITE)
        self.screen.blit(score_text, (SCREEN_WIDTH - 200, SCREEN_HEIGHT - 70))

        # Уровень
        level_text = self.font.render(f"LEVEL: {self.current_level}", True, WHITE)
        self.screen.blit(level_text, (SCREEN_WIDTH - 200, SCREEN_HEIGHT - 40))

        # Враги
        enemies_alive = len([e for e in self.enemies if e.is_alive])
        enemies_text = self.font.render(f"ENEMIES: {enemies_alive}", True, RED)
        self.screen.blit(enemies_text, (SCREEN_WIDTH - 400, SCREEN_HEIGHT - 55))

    def render_minimap(self):
        """Рендерим мини-карту"""
        map_scale = 8
        map_offset_x = 10
        map_offset_y = 10

        # Фон карты
        map_width = len(self.walls[0]) * map_scale
        map_height = len(self.walls) * map_scale
        map_surface = pygame.Surface((map_width, map_height))
        map_surface.fill((0, 0, 0))
        map_surface.set_alpha(180)

        # Рисуем стены
        for y, row in enumerate(self.walls):
            for x, cell in enumerate(row):
                if cell > 0:
                    color = (100, 100, 100) if cell == 1 else (80, 80, 100) if cell == 2 else (100, 80, 80)
                    pygame.draw.rect(map_surface, color,
                                     (x * map_scale, y * map_scale, map_scale - 1, map_scale - 1))

        # Рисуем врагов
        for enemy in self.enemies:
            if enemy.is_alive:
                pygame.draw.circle(map_surface, enemy.color,
                                   (int(enemy.pos.x * map_scale), int(enemy.pos.y * map_scale)), 3)

        # Рисуем предметы
        for pickup in self.pickups:
            if pickup.is_active:
                pygame.draw.circle(map_surface, pickup.color,
                                   (int(pickup.pos.x * map_scale), int(pickup.pos.y * map_scale)), 2)

        # Рисуем игрока
        player_x = int(self.player.pos.x * map_scale)
        player_y = int(self.player.pos.y * map_scale)
        pygame.draw.circle(map_surface, GREEN, (player_x, player_y), 3)

        # Направление взгляда
        look_x = player_x + int(math.cos(self.player.angle) * 10)
        look_y = player_y + int(math.sin(self.player.angle) * 10)
        pygame.draw.line(map_surface, GREEN, (player_x, player_y), (look_x, look_y), 2)

        self.screen.blit(map_surface, (map_offset_x, map_offset_y))

    def render_menu(self):
        """Рендерим главное меню"""
        self.screen.fill(BLACK)

        # Заголовок
        title = self.big_font.render("DOOM", True, RED)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 150))
        self.screen.blit(title, title_rect)

        subtitle = self.font.render("Python Edition", True, WHITE)
        subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 220))
        self.screen.blit(subtitle, subtitle_rect)

        # Пункты меню
        menu_items = [
            "Press ENTER to Start",
            "",
            "Controls:",
            "WASD - Move",
            "Mouse - Look",
            "Left Click - Shoot",
            "ESC - Pause",
            "",
            "Press Q to Quit"
        ]

        for i, item in enumerate(menu_items):
            text = self.font.render(item, True, WHITE if i == 0 else LIGHT_GRAY)
            text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, 320 + i * 35))
            self.screen.blit(text, text_rect)

    def render_pause(self):
        """Рендерим меню паузы"""
        # Затемнение
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill(BLACK)
        overlay.set_alpha(150)
        self.screen.blit(overlay, (0, 0))

        # Текст
        pause_text = self.big_font.render("PAUSED", True, WHITE)
        pause_rect = pause_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
        self.screen.blit(pause_text, pause_rect)

        resume_text = self.font.render("Press ESC to Resume", True, WHITE)
        resume_rect = resume_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
        self.screen.blit(resume_text, resume_rect)

        menu_text = self.font.render("Press M for Main Menu", True, WHITE)
        menu_rect = menu_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60))
        self.screen.blit(menu_text, menu_rect)

    def render_game_over(self):
        """Рендерим экран поражения"""
        self.screen.fill((50, 0, 0))

        title = self.big_font.render("GAME OVER", True, RED)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
        self.screen.blit(title, title_rect)

        score_text = self.font.render(f"Final Score: {self.player.score}", True, WHITE)
        score_rect = score_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
        self.screen.blit(score_text, score_rect)

        restart_text = self.font.render("Press R to Restart or M for Menu", True, WHITE)
        restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 70))
        self.screen.blit(restart_text, restart_rect)

    def render_victory(self):
        """Рендерим экран победы"""
        self.screen.fill((0, 50, 0))

        title = self.big_font.render("VICTORY!", True, GREEN)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
        self.screen.blit(title, title_rect)

        score_text = self.font.render(f"Final Score: {self.player.score}", True, WHITE)
        score_rect = score_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
        self.screen.blit(score_text, score_rect)

        restart_text = self.font.render("Press R to Play Again or M for Menu", True, WHITE)
        restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 70))
        self.screen.blit(restart_text, restart_rect)

    def handle_shooting(self, current_time: float):
        """Обработка стрельбы"""
        if self.player.weapon.fire(current_time):
            # Проверяем попадание по врагам
            for enemy in self.enemies:
                if not enemy.is_alive:
                    continue

                # Вычисляем угол к врагу
                dx = enemy.pos.x - self.player.pos.x
                dy = enemy.pos.y - self.player.pos.y
                distance = math.sqrt(dx * dx + dy * dy)

                theta = math.atan2(dy, dx)
                gamma = theta - self.player.angle

                # Нормализация угла
                while gamma > math.pi:
                    gamma -= 2 * math.pi
                while gamma < -math.pi:
                    gamma += 2 * math.pi

                # Проверяем попадание (в центре экрана)
                hit_tolerance = 0.3  # Радиус попадания
                if abs(gamma) < hit_tolerance and distance < 15:
                    # Проверяем, нет ли стены между игроком и врагом
                    if not self.is_wall_between(self.player.pos, enemy.pos):
                        killed = enemy.take_damage(self.player.weapon.damage)
                        if killed:
                            self.player.score += 100
                            self.player.kills += 1
                        break  # Попадаем только в одного врага

    def is_wall_between(self, pos1: Vector2, pos2: Vector2) -> bool:
        """Проверяет, есть ли стена между двумя точками"""
        dx = pos2.x - pos1.x
        dy = pos2.y - pos1.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance == 0:
            return False

        steps = int(distance * 10)
        for i in range(steps):
            t = i / steps
            check_x = pos1.x + dx * t
            check_y = pos1.y + dy * t

            map_x = int(check_x)
            map_y = int(check_y)

            if 0 <= map_x < len(self.walls[0]) and 0 <= map_y < len(self.walls):
                if self.walls[map_y][map_x] > 0:
                    return True

        return False

    def check_pickups(self):
        """Проверяем подбор предметов"""
        for pickup in self.pickups:
            if not pickup.is_active:
                continue

            distance = self.player.pos.distance_to(pickup.pos)
            if distance < 0.5:
                pickup.is_active = False

                if pickup.pickup_type == "health":
                    self.player.heal(pickup.value)
                    self.player.score += 10
                elif pickup.pickup_type == "ammo":
                    self.player.add_ammo(pickup.value)
                    self.player.score += 10
                elif pickup.pickup_type == "armor":
                    self.player.add_armor(pickup.value)
                    self.player.score += 20

    def update_enemies(self, delta_time: float, current_time: float):
        """Обновляем врагов"""
        for enemy in self.enemies:
            enemy.update(self.player.pos, self.walls, delta_time, current_time)

            # Проверяем атаку
            if enemy.can_attack(self.player.pos, current_time):
                damage = enemy.attack(current_time)
                if self.player.take_damage(damage):
                    self.game_state = "game_over"

    def check_level_complete(self):
        """Проверяем, завершён ли уровень"""
        enemies_alive = len([e for e in self.enemies if e.is_alive])
        if enemies_alive == 0:
            if self.current_level < self.max_level:
                self.current_level += 1
                self.load_level(self.current_level)
                self.player.score += 500  # Бонус за уровень
            else:
                self.game_state = "victory"

    def handle_input(self, delta_time: float):
        """Обработка ввода"""
        keys = pygame.key.get_pressed()

        # Движение
        forward = 0
        strafe = 0

        if keys[pygame.K_w]:
            forward = 1
        if keys[pygame.K_s]:
            forward = -1
        if keys[pygame.K_a]:
            strafe = -1
        if keys[pygame.K_d]:
            strafe = 1

        if forward != 0 or strafe != 0:
            self.player.move(forward, strafe, self.walls, delta_time)

        # Поворот мышью
        mouse_rel = pygame.mouse.get_rel()
        if mouse_rel[0] != 0:
            self.player.rotate(mouse_rel[0] * 0.002, 1)

        # Стрельба
        mouse_buttons = pygame.mouse.get_pressed()
        if mouse_buttons[0]:  # Левая кнопка мыши
            current_time = pygame.time.get_ticks() / 1000
            self.handle_shooting(current_time)

    def run(self):
        """Главный игровой цикл"""
        running = True
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)

        while running:
            delta_time = self.clock.tick(60) / 1000
            current_time = pygame.time.get_ticks() / 1000

            # Обработка событий
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if self.game_state == "menu":
                        if event.key == pygame.K_RETURN:
                            self.game_state = "playing"
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                        elif event.key == pygame.K_q:
                            running = False

                    elif self.game_state == "playing":
                        if event.key == pygame.K_ESCAPE:
                            self.game_state = "paused"
                            pygame.mouse.set_visible(True)
                            pygame.event.set_grab(False)

                    elif self.game_state == "paused":
                        if event.key == pygame.K_ESCAPE:
                            self.game_state = "playing"
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                        elif event.key == pygame.K_m:
                            self.game_state = "menu"
                            self.current_level = 1
                            self.load_level(1)

                    elif self.game_state in ["game_over", "victory"]:
                        if event.key == pygame.K_r:
                            self.current_level = 1
                            self.load_level(1)
                            self.game_state = "playing"
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                        elif event.key == pygame.K_m:
                            self.game_state = "menu"
                            self.current_level = 1
                            self.load_level(1)

            # Обновление и рендеринг
            if self.game_state == "menu":
                self.render_menu()
                pygame.mouse.set_visible(True)
                pygame.event.set_grab(False)

            elif self.game_state == "playing":
                # Обновление
                self.handle_input(delta_time)
                self.player.weapon.update(current_time)
                self.update_enemies(delta_time, current_time)
                self.check_pickups()
                self.check_level_complete()

                # Рендеринг
                z_buffer = self.render_3d()
                self.render_sprites(z_buffer)
                self.render_weapon()
                self.render_hud()
                self.render_minimap()

            elif self.game_state == "paused":
                z_buffer = self.render_3d()
                self.render_sprites(z_buffer)
                self.render_weapon()
                self.render_hud()
                self.render_pause()

            elif self.game_state == "game_over":
                self.render_game_over()
                pygame.mouse.set_visible(True)
                pygame.event.set_grab(False)

            elif self.game_state == "victory":
                self.render_victory()
                pygame.mouse.set_visible(True)
                pygame.event.set_grab(False)

            # FPS
            fps_text = self.font.render(f"FPS: {int(self.clock.get_fps())}", True, WHITE)
            self.screen.blit(fps_text, (SCREEN_WIDTH - 100, 10))

            pygame.display.flip()

        pygame.quit()


if __name__ == "__main__":
    game = DoomGame()
    game.run()