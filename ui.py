"""
ui.py

Presentation layer for The Shifting Grove.

This module contains the visual feedback systems used by the main maze game:
- gameplay HUD elements
- shard and life counters
- Grove Shift meter display
- temporary toast messages
- reward effect timers
- player spawn glow
- shard and portal sparkle effects
- mist particles and Grove Shift transition overlays

Keeping these systems in ui.py allows game.py to focus on state coordination and
core gameplay logic while this file handles presentation, readability, and game
feel.
"""

import math
import random

import pygame

from asset_loader import load_image

from settings import (
    MIST_PARTICLE_COLOR,
    MIST_VEIL_COLOR,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SHARD_COUNT,
    TEXT_COLOR,
    TOAST_DURATION_FRAMES,
    PLAYER_START_GLOW_FRAMES,
)

class ImageButton:
    """
    Clickable image-based button used by the title and mode selection screens.

    Each button supports a normal image and an optional hover image. Images are
    scaled to fit within a target size while preserving their original aspect
    ratio.
    """

    def __init__(self, x, y, normal_image_path, hover_image_path=None, size=None):
        self.size = size

        raw_normal_image = load_image(
            normal_image_path,
            use_alpha=True,
        )

        if hover_image_path:
            raw_hover_image = load_image(
                hover_image_path,
                use_alpha=True,
            )
        else:
            raw_hover_image = raw_normal_image

        if raw_normal_image is None:
            raise ValueError(f"Could not load button image: {normal_image_path}")

        if raw_hover_image is None:
            raw_hover_image = raw_normal_image

        self.normal_image = self.scale_image_to_fit(raw_normal_image, size)
        self.hover_image = self.scale_image_to_fit(raw_hover_image, size)

        self.rect = self.normal_image.get_rect(topleft=(x, y))
        self.is_hovered = False

    def scale_image_to_fit(self, image, max_size):
        """Scales an image to fit inside max_size without stretching it."""
        if image is None:
            return None

        if max_size is None:
            return image

        max_width, max_height = max_size

        original_width = image.get_width()
        original_height = image.get_height()

        if original_width == 0 or original_height == 0:
            return image

        width_ratio = max_width / original_width
        height_ratio = max_height / original_height
        scale_ratio = min(width_ratio, height_ratio)

        new_width = int(original_width * scale_ratio)
        new_height = int(original_height * scale_ratio)

        return pygame.transform.smoothscale(image, (new_width, new_height))

    def update(self):
        """Updates whether the mouse is currently hovering over the button."""
        mouse_position = pygame.mouse.get_pos()
        self.is_hovered = self.rect.collidepoint(mouse_position)

    def draw(self, screen):
        """Draws the normal or hover button image."""
        image = self.hover_image if self.is_hovered else self.normal_image
        screen.blit(image, self.rect)

    def is_clicked(self, event):
        """Returns True if the button was clicked with the left mouse button."""
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )


class MistParticle:
    """Represents one soft flowing wind-like mist wisp."""

    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.reset(randomize_position=True)

    def reset(self, randomize_position=False):
        """Resets the mist wisp."""
        if randomize_position:
            self.x = random.randint(-320, self.screen_width)
            self.y = random.randint(70, self.screen_height - 70)
        else:
            self.x = random.randint(-460, -220)
            self.y = random.randint(70, self.screen_height - 70)

        self.length = random.randint(360, 620)
        self.thickness = random.randint(10, 22)

        self.speed_x = random.uniform(0.75, 1.55)
        self.speed_y = random.uniform(-0.035, 0.035)

        # A small curve amount keeps it organic without looking like a sine wave.
        self.curve_offset = random.randint(-55, 55)
        self.secondary_curve = random.randint(-18, 18)

        self.alpha = random.randint(55, 95)
        self.drift_phase = random.uniform(0, math.tau)

    def update(self):
        """Moves the mist wisp slowly across the screen."""
        self.x += self.speed_x
        self.y += self.speed_y

        # Very subtle vertical breathing, not a visible wave.
        self.drift_phase += 0.006
        self.y += math.sin(self.drift_phase) * 0.035

        if self.x > self.screen_width + 120:
            self.reset(randomize_position=False)

    def get_bezier_point(self, t):
        """Returns a point along a gentle cubic Bézier curve."""
        start_x = self.x
        start_y = self.y

        control_1_x = self.x + self.length * 0.30
        control_1_y = self.y + self.curve_offset

        control_2_x = self.x + self.length * 0.72
        control_2_y = self.y + self.secondary_curve

        end_x = self.x + self.length
        end_y = self.y + self.curve_offset * 0.18

        one_minus_t = 1 - t

        x = (
            one_minus_t ** 3 * start_x
            + 3 * one_minus_t ** 2 * t * control_1_x
            + 3 * one_minus_t * t ** 2 * control_2_x
            + t ** 3 * end_x
        )

        y = (
            one_minus_t ** 3 * start_y
            + 3 * one_minus_t ** 2 * t * control_1_y
            + 3 * one_minus_t * t ** 2 * control_2_y
            + t ** 3 * end_y
        )

        return int(x), int(y)

    def draw(self, surface, mist_strength):
        """Draws a smooth tapered mist wisp."""
        visibility = min(mist_strength / 255, 1)
        base_alpha = int(self.alpha * visibility)

        if base_alpha <= 0:
            return

        point_count = 34

        # Outer soft body.
        for index in range(point_count):
            t = index / max(point_count - 1, 1)
            x, y = self.get_bezier_point(t)

            # Smooth taper: thin ends, fuller middle.
            taper = math.sin(t * math.pi)

            if taper <= 0:
                continue

            radius_x = max(4, int(self.thickness * 2.8 * taper))
            radius_y = max(2, int(self.thickness * 0.55 * taper))

            alpha = int(base_alpha * 0.58 * taper)

            pygame.draw.ellipse(
                surface,
                (*MIST_PARTICLE_COLOR, alpha),
                (
                    x - radius_x,
                    y - radius_y,
                    radius_x * 2,
                    radius_y * 2,
                ),
            )

        # Inner brighter stream, much thinner.
        for index in range(point_count):
            t = index / max(point_count - 1, 1)
            x, y = self.get_bezier_point(t)

            taper = math.sin(t * math.pi)

            if taper <= 0:
                continue

            radius_x = max(3, int(self.thickness * 1.45 * taper))
            radius_y = max(1, int(self.thickness * 0.22 * taper))

            alpha = int(base_alpha * 0.48 * taper)

            pygame.draw.ellipse(
                surface,
                (255, 255, 255, alpha),
                (
                    x - radius_x,
                    y - radius_y,
                    radius_x * 2,
                    radius_y * 2,
                ),
            )



class MistSystem:
    """Manages the flowing mist layer used during Grove Shift transitions."""

    def __init__(self, screen_width, screen_height, particle_count):
        self.screen_width = screen_width
        self.screen_height = screen_height

        wisp_count = min(particle_count, 14)

        self.particles = [
            MistParticle(screen_width, screen_height)
            for _ in range(wisp_count)
        ]

    def update(self):
        """Updates all mist particles."""
        for particle in self.particles:
            particle.update()

    def draw(self, screen, mist_strength):
        """Draws the full moving mist layer."""
        mist_layer = pygame.Surface(
            (self.screen_width, self.screen_height),
            pygame.SRCALPHA,
        )

        # Strong base veil keeps transitions from flashing between screens.
        base_alpha = int(95 * min(mist_strength / 255, 1))
        mist_layer.fill((*MIST_VEIL_COLOR, base_alpha))

        for particle in self.particles:
            particle.draw(mist_layer, mist_strength)

        screen.blit(mist_layer, (0, 0))

        # Second softer pass gives the mist a layered, airy look.
        base_alpha = int(42 * min(mist_strength / 255, 1))
        mist_layer.fill((*MIST_VEIL_COLOR, base_alpha))

        for particle in self.particles:
            particle.draw(mist_layer, mist_strength)

        screen.blit(mist_layer, (0, 0))




class SparkleParticle:
    """Small fading particle used for shard and portal feedback effects."""

    def __init__(self, x, y, color, speed_scale=1.0):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(1.2, 3.4) * speed_scale

        self.x = x
        self.y = y
        self.dx = math.cos(angle) * speed
        self.dy = math.sin(angle) * speed

        self.radius = random.randint(2, 4)
        self.life = random.randint(28, 46)
        self.max_life = self.life
        self.color = color

    @property
    def alive(self):
        """Returns True while the particle should remain active."""
        return self.life > 0

    def update(self):
        """Moves and fades the particle."""
        self.x += self.dx
        self.y += self.dy
        self.dy -= 0.015
        self.life -= 1

    def draw(self, screen):
        """Draws the sparkle particle."""
        if self.life <= 0:
            return

        fade = self.life / self.max_life
        alpha = int(230 * fade)
        radius = max(1, int(self.radius * fade))

        sparkle_surface = pygame.Surface((16, 16), pygame.SRCALPHA)

        pygame.draw.circle(
            sparkle_surface,
            (*self.color, alpha),
            (8, 8),
            radius,
        )

        pygame.draw.circle(
            sparkle_surface,
            (255, 255, 255, int(alpha * 0.75)),
            (8, 8),
            max(1, radius // 2),
        )

        screen.blit(sparkle_surface, (int(self.x) - 8, int(self.y) - 8))




class ToastMessage:
    """Temporary message shown to the player with a smooth fade in/out."""

    def __init__(self, text, duration=TOAST_DURATION_FRAMES):
        self.text = text
        self.duration = duration
        self.timer = duration

    @property
    def alive(self):
        """Returns True while the toast should be displayed."""
        return self.timer > 0

    def update(self):
        """Counts the toast down."""
        if self.timer > 0:
            self.timer -= 1

    def get_alpha(self):
        """Calculates fade alpha for the toast message."""
        if self.duration <= 0:
            return 0

        progress = self.timer / self.duration

        if progress > 0.82:
            return int((1 - progress) / 0.18 * 220)

        if progress < 0.22:
            return int(progress / 0.22 * 220)

        return 220


class GameUI:
    """Coordinates HUD, toast messages, particles, and transition visuals."""

    def __init__(
        self,
        screen_width,
        screen_height,
        mist_particle_count,
        shard_icon,
        heart_full_icon,
        heart_empty_icon,
        large_font,
        medium_font,
        small_font,
        tiny_font,
    ):
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.shard_icon = shard_icon
        self.heart_full_icon = heart_full_icon
        self.heart_empty_icon = heart_empty_icon

        self.large_font = large_font
        self.medium_font = medium_font
        self.small_font = small_font
        self.tiny_font = tiny_font

        self.mist_system = MistSystem(
            screen_width,
            screen_height,
            particle_count=mist_particle_count,
        )

        self.sparkles = []
        self.toasts = []

        self.player_spawn_glow_timer = 0
        self.portal_activation_timer = 0

    # -----------------------------
    # Update methods
    # -----------------------------

    def reset_level_feedback(self):
        """Resets level-specific UI feedback when a new maze begins."""
        self.player_spawn_glow_timer = PLAYER_START_GLOW_FRAMES
        self.portal_activation_timer = 0
        self.sparkles.clear()
        self.toasts.clear()

    def update(self):
        """Updates all non-transition UI effects."""
        self.update_sparkles()
        self.update_toasts()

        if self.player_spawn_glow_timer > 0:
            self.player_spawn_glow_timer -= 1

        if self.portal_activation_timer > 0:
            self.portal_activation_timer -= 1

    def update_transition(self):
        """Updates transition-specific visuals."""
        self.mist_system.update()

    def update_sparkles(self):
        """Updates sparkle particles and removes finished particles."""
        for sparkle in self.sparkles:
            sparkle.update()

        self.sparkles = [sparkle for sparkle in self.sparkles if sparkle.alive]

    def update_toasts(self):
        """Updates toast messages and removes expired messages."""
        for toast in self.toasts:
            toast.update()

        self.toasts = [toast for toast in self.toasts if toast.alive]

    # -----------------------------
    # Event feedback methods
    # -----------------------------

    def show_toast(self, text, duration=TOAST_DURATION_FRAMES):
        """Shows a short message to the player."""
        self.toasts.append(ToastMessage(text, duration))

        if len(self.toasts) > 2:
            self.toasts.pop(0)

    def create_shard_collection_feedback(self, center):
        """Creates sparkle feedback when a shard is collected."""
        colors = [
            (140, 230, 255),
            (210, 250, 255),
            (255, 255, 255),
            (170, 220, 255),
        ]

        for _ in range(24):
            color = random.choice(colors)
            self.sparkles.append(
                SparkleParticle(
                    center[0],
                    center[1],
                    color=color,
                    speed_scale=1.0,
                )
            )

        self.show_toast("Shard Collected", duration=85)

    def create_portal_activation_feedback(self, center):
        """Creates a stronger glow/sparkle burst when the portal awakens."""
        colors = [
            (170, 245, 255),
            (220, 255, 245),
            (255, 255, 255),
            (120, 210, 255),
        ]

        for _ in range(46):
            color = random.choice(colors)
            self.sparkles.append(
                SparkleParticle(
                    center[0],
                    center[1],
                    color=color,
                    speed_scale=1.35,
                )
            )

        self.portal_activation_timer = 120
        self.show_toast("Portal Ready!", duration=130)

    # -----------------------------
    # Draw methods
    # -----------------------------

    def draw_gameplay_ui(
        self,
        screen,
        shards_collected,
        portal_is_active,
        player,
        player_lives,
        max_lives,
        grove_shift_meter,
        grove_shift_max,
        portal_rect=None,
        fox_banish_timer=0,
        shadow_rush_timer=0,
        portal_flicker_timer=0,
        fps=60,
    ):
        """Draws all gameplay presentation elements for the active maze."""
        self.draw_player_spawn_glow(screen, player)
        self.draw_sparkles(screen)
        self.draw_portal_activation_glow(screen, portal_rect)

        self.draw_hud(
            screen=screen,
            shards_collected=shards_collected,
            portal_is_active=portal_is_active,
            player_lives=player_lives,
            max_lives=max_lives,
            grove_shift_meter=grove_shift_meter,
            grove_shift_max=grove_shift_max,
        )

        self.draw_active_effect_timers(
            screen=screen,
            fox_banish_timer=fox_banish_timer,
            shadow_rush_timer=shadow_rush_timer,
            portal_flicker_timer=portal_flicker_timer,
            fps=fps,
        )

        self.draw_toasts(screen)

    def draw_hud(
        self,
        screen,
        shards_collected,
        portal_is_active,
        player_lives,
        max_lives,
        grove_shift_meter,
        grove_shift_max,
    ):
        """Draws the compact gameplay HUD for lives, shards, and Grove Shift."""
        self.draw_lives_hud(screen, player_lives, max_lives)
        self.draw_grove_shift_hud(screen, grove_shift_meter, grove_shift_max)
        self.draw_shard_hud(screen, shards_collected, portal_is_active)

        if portal_is_active:
            self.draw_portal_ready_indicator(screen)

    def draw_active_effect_timers(
        self,
        screen,
        fox_banish_timer=0,
        shadow_rush_timer=0,
        portal_flicker_timer=0,
        fps=60,
    ):
        """Draws active temporary reward effect timers as clean top-right text."""
        active_effects = []

        if fox_banish_timer > 0:
            active_effects.append(("FOX BANISHED", fox_banish_timer))

        if portal_flicker_timer > 0:
            active_effects.append(("PORTAL FLICKER", portal_flicker_timer))

        if shadow_rush_timer > 0:
            active_effects.append(("SHADOW RUSH", shadow_rush_timer))

        if not active_effects:
            return

        start_x = self.screen_width - 24
        start_y = 4
        line_spacing = 26

        for index, (label, timer_value) in enumerate(active_effects):
            seconds_left = max(0, timer_value / max(fps, 1))
            text = f"{label}: {seconds_left:.1f}s"

            y = start_y + index * line_spacing

            # Small dark shadow keeps the timer readable over the maze.
            shadow_surface = self.tiny_font.render(text, True, (25, 20, 35))
            shadow_rect = shadow_surface.get_rect(topright=(start_x + 2, y + 2))
            screen.blit(shadow_surface, shadow_rect)

            text_surface = self.tiny_font.render(text, True, (255, 255, 255))
            text_rect = text_surface.get_rect(topright=(start_x, y))
            screen.blit(text_surface, text_rect)

    def draw_lives_hud(self, screen, player_lives, max_lives):
        """
        Draws player lives in the top-left corner.

        Uses heart image assets if available. If the assets are missing, falls back
        to simple drawn hearts so the game still runs.
        """
        start_x = 20
        start_y = 2
        spacing = 34

        for i in range(max_lives):
            heart_x = start_x + i * spacing
            filled = i < player_lives

            if filled and self.heart_full_icon:
                screen.blit(self.heart_full_icon, (heart_x, start_y))

            elif not filled and self.heart_empty_icon:
                screen.blit(self.heart_empty_icon, (heart_x, start_y))

            else:
                self.draw_heart_icon(screen, heart_x, start_y, filled)

    def draw_grove_shift_hud(self, screen, grove_shift_meter, grove_shift_max):
        """
        Draws the Grove Shift meter in the bottom-right as a compact HUD panel.

        This keeps it away from the top maze area and makes the label easier to
        read without being squeezed.
        """
        panel_width = 245
        panel_height = 46

        panel_x = self.screen_width - panel_width - 18
        panel_y = self.screen_height - panel_height - 8

        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)

        pygame.draw.rect(
            screen,
            (18, 16, 32),
            panel_rect,
            border_radius=12,
        )

        pygame.draw.rect(
            screen,
            (170, 145, 225),
            panel_rect,
            2,
            border_radius=12,
        )

        percent_value = 0
        if grove_shift_max > 0:
            percent_value = int(max(0, min(grove_shift_meter / grove_shift_max, 1)) * 100)

        label_surface = self.tiny_font.render(
            "Grove Shift",
            True,
            (240, 235, 255),
        )

        percent_surface = self.tiny_font.render(
            f"{percent_value}%",
            True,
            (240, 235, 255),
        )

        label_rect = label_surface.get_rect(
            midleft=(panel_rect.x + 12, panel_rect.y + 14)
        )

        percent_rect = percent_surface.get_rect(
            midright=(panel_rect.right - 12, panel_rect.y + 14)
        )

        screen.blit(label_surface, label_rect)
        screen.blit(percent_surface, percent_rect)

        bar_x = panel_rect.x + 12
        bar_y = panel_rect.y + 28
        bar_width = panel_width - 24
        bar_height = 10

        bar_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)

        pygame.draw.rect(
            screen,
            (35, 30, 55),
            bar_rect,
            border_radius=6,
        )

        pygame.draw.rect(
            screen,
            (105, 95, 150),
            bar_rect,
            1,
            border_radius=6,
        )

        fill_ratio = 0
        if grove_shift_max > 0:
            fill_ratio = max(0, min(grove_shift_meter / grove_shift_max, 1))

        fill_width = int(bar_width * fill_ratio)

        if fill_width > 0:
            fill_rect = pygame.Rect(bar_x, bar_y, fill_width, bar_height)

            pygame.draw.rect(
                screen,
                (125, 80, 210),
                fill_rect,
                border_radius=6,
            )

            highlight_rect = pygame.Rect(
                fill_rect.x + 2,
                fill_rect.y + 1,
                max(0, fill_rect.width - 4),
                3,
            )

            if highlight_rect.width > 0:
                pygame.draw.rect(
                    screen,
                    (210, 175, 255),
                    highlight_rect,
                    border_radius=2,
                )

            glow_surface = pygame.Surface(
                (fill_rect.width, fill_rect.height + 8),
                pygame.SRCALPHA,
            )
            glow_surface.fill((170, 120, 255, 45))
            screen.blit(glow_surface, (fill_rect.x, fill_rect.y - 4))

    def draw_heart_icon(self, screen, x, y, filled=True):
        """Draws one heart icon."""
        heart_surface = pygame.Surface((28, 26), pygame.SRCALPHA)

        if filled:
            left_color = (255, 110, 150)
            right_color = (235, 85, 130)
            outline = (255, 225, 235)
        else:
            left_color = (110, 135, 150)
            right_color = (90, 115, 130)
            outline = (190, 205, 215)

        pygame.draw.circle(heart_surface, left_color, (9, 8), 6)
        pygame.draw.circle(heart_surface, right_color, (18, 8), 6)

        pygame.draw.polygon(
            heart_surface,
            right_color,
            [(3, 10), (24, 10), (14, 23)],
        )

        pygame.draw.circle(heart_surface, outline, (9, 8), 6, 2)
        pygame.draw.circle(heart_surface, outline, (18, 8), 6, 2)
        pygame.draw.lines(
            heart_surface,
            outline,
            False,
            [(3, 10), (14, 23), (24, 10)],
            2,
        )

        screen.blit(heart_surface, (x, y))

    def draw_shard_hud(self, screen, shards_collected, portal_is_active):
        """Draws the Grove Shard counter in the bottom-left corner."""
        panel_width = 96
        panel_height = 30

        panel_rect = pygame.Rect(
            20,
            SCREEN_HEIGHT - panel_height - 14,
            panel_width,
            panel_height,
        )

        panel_surface = pygame.Surface(
            (panel_rect.width, panel_rect.height),
            pygame.SRCALPHA,
        )
        panel_surface.fill((35, 75, 95, 120))

        screen.blit(panel_surface, panel_rect)

        pygame.draw.rect(
            screen,
            (180, 230, 250),
            panel_rect,
            2,
            border_radius=9,
        )

        icon_x = panel_rect.x + 8
        icon_y = panel_rect.y + 3

        if self.shard_icon:
            screen.blit(self.shard_icon, (icon_x, icon_y))
        else:
            self.draw_hud_shard_fallback(screen, icon_x + 12, icon_y + 12)

        counter_surface = self.tiny_font.render(
            f"{shards_collected}/{SHARD_COUNT}",
            True,
            (255, 255, 255),
        )

        screen.blit(counter_surface, (panel_rect.x + 42, panel_rect.y + 4))

    def draw_hud_shard_fallback(self, screen, center_x, center_y):
        """Draws a small fallback shard icon if the image asset is missing."""
        points = [
            (center_x, center_y - 11),
            (center_x + 8, center_y),
            (center_x, center_y + 11),
            (center_x - 8, center_y),
        ]

        pygame.draw.polygon(screen, (150, 230, 255), points)
        pygame.draw.polygon(screen, (245, 255, 255), points, 2)

    def draw_portal_ready_indicator(self, screen):
        """Draws a compact portal-ready badge beside the shard counter."""
        text_surface = self.tiny_font.render(
            "Portal Ready",
            True,
            (225, 255, 250),
        )

        text_rect = text_surface.get_rect()
        text_rect.topleft = (126, SCREEN_HEIGHT - 39)

        badge_rect = text_rect.inflate(16, 8)

        badge_surface = pygame.Surface(
            (badge_rect.width, badge_rect.height),
            pygame.SRCALPHA,
        )
        badge_surface.fill((35, 105, 100, 115))

        screen.blit(badge_surface, badge_rect)

        pygame.draw.rect(
            screen,
            (180, 250, 235),
            badge_rect,
            2,
            border_radius=8,
        )

        screen.blit(text_surface, text_rect)

    def draw_toasts(self, screen):
        """Draws the most recent toast message near the bottom center."""
        if not self.toasts:
            return

        toast = self.toasts[-1]
        alpha = toast.get_alpha()

        if alpha <= 0:
            return

        message_surface = self.tiny_font.render(
            toast.text,
            True,
            TEXT_COLOR,
        )
        message_surface.set_alpha(alpha)

        message_rect = message_surface.get_rect(
            center=(SCREEN_WIDTH // 2 - 90, SCREEN_HEIGHT - 36)
        )

        box_rect = message_rect.inflate(28, 12)

        box_surface = pygame.Surface(
            (box_rect.width, box_rect.height),
            pygame.SRCALPHA,
        )
        box_surface.fill((35, 80, 105, int(alpha * 0.68)))

        screen.blit(box_surface, box_rect)

        pygame.draw.rect(
            screen,
            (185, 235, 255, alpha),
            box_rect,
            2,
            border_radius=10,
        )

        screen.blit(message_surface, message_rect)

    def draw_player_spawn_glow(self, screen, player):
        """Draws a temporary glow around the player when a level begins."""
        if self.player_spawn_glow_timer <= 0:
            return

        progress = self.player_spawn_glow_timer / PLAYER_START_GLOW_FRAMES
        pulse = math.sin(pygame.time.get_ticks() * 0.008) * 5

        glow_alpha = int(95 * progress)
        ring_alpha = int(180 * progress)

        glow_radius = int(34 + pulse)
        ring_radius = int(42 + pulse)

        glow_surface_size = 110
        glow_surface = pygame.Surface(
            (glow_surface_size, glow_surface_size),
            pygame.SRCALPHA,
        )

        center = (glow_surface_size // 2, glow_surface_size // 2)

        pygame.draw.circle(
            glow_surface,
            (120, 220, 255, glow_alpha),
            center,
            glow_radius,
        )

        pygame.draw.circle(
            glow_surface,
            (235, 255, 255, ring_alpha),
            center,
            ring_radius,
            2,
        )

        glow_x = player.rect.centerx - glow_surface_size // 2
        glow_y = player.rect.centery - glow_surface_size // 2

        screen.blit(glow_surface, (glow_x, glow_y))

    def draw_sparkles(self, screen):
        """Draws all active sparkle particles."""
        for sparkle in self.sparkles:
            sparkle.draw(screen)

    def draw_portal_activation_glow(self, screen, portal_rect):
        """Draws a temporary glow at the portal after it activates."""
        if self.portal_activation_timer <= 0 or portal_rect is None:
            return

        progress = self.portal_activation_timer / 120
        pulse = math.sin(pygame.time.get_ticks() * 0.01) * 5

        glow_alpha = int(100 * progress)
        ring_alpha = int(190 * progress)

        glow_radius = int(52 + pulse)
        ring_radius = int(68 + pulse)

        glow_surface_size = 170
        glow_surface = pygame.Surface(
            (glow_surface_size, glow_surface_size),
            pygame.SRCALPHA,
        )

        center = (glow_surface_size // 2, glow_surface_size // 2)

        pygame.draw.circle(
            glow_surface,
            (120, 235, 255, glow_alpha),
            center,
            glow_radius,
        )

        pygame.draw.circle(
            glow_surface,
            (230, 255, 250, ring_alpha),
            center,
            ring_radius,
            3,
        )

        glow_x = portal_rect.centerx - glow_surface_size // 2
        glow_y = portal_rect.centery - glow_surface_size // 2

        screen.blit(glow_surface, (glow_x, glow_y))

    def draw_transition(self, screen, transition_alpha):
        """Draws the full grove-shifting transition with opaque flowing wind mist."""
        # Main opaque fog wash.
        mist_veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        mist_veil.fill((*MIST_VEIL_COLOR, transition_alpha))
        screen.blit(mist_veil, (0, 0))

        # Flowing ribbon mist.
        self.mist_system.draw(screen, transition_alpha)

        # Slight darkening so text stays readable.
        dim_layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim_layer.fill((0, 0, 0, int(transition_alpha * 0.12)))
        screen.blit(dim_layer, (0, 0))

        self.draw_transition_text(screen, transition_alpha)

    def draw_transition_text(self, screen, transition_alpha):
        """Draws the transition text with a stable magical glow."""
        if transition_alpha < 60:
            return

        text_alpha = min(transition_alpha, 255)

        message_text = "The Grove is Shifting..."

        glow = self.medium_font.render(
            message_text,
            True,
            (120, 180, 220),
        )
        glow.set_alpha(int(text_alpha * 0.75))

        message = self.medium_font.render(
            message_text,
            True,
            (255, 255, 255),
        )
        message.set_alpha(text_alpha)

        center_position = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

        glow_rect = glow.get_rect(
            center=(center_position[0] + 3, center_position[1] + 3)
        )
        message_rect = message.get_rect(center=center_position)

        screen.blit(glow, glow_rect)
        screen.blit(message, message_rect)