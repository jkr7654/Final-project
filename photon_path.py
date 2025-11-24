import pygame
import math
import random

pygame.init()

W, H = 1000, 600
screen = pygame.display.set_mode((W, H))
clock = pygame.time.Clock()
pygame.display.set_caption("Photon Paths")

# Black hole
bh_x, bh_y = W//2, H//2
bh_radius = 40     # size (affects gravity strength)
gravity_base = 12000  # stronger gravity for realism

# Photon lines
LINES = 35
POINTS = 180
lines = []

for _ in range(LINES):
    line = []
    y = random.randint(0, H)
    for i in range(POINTS):
        x = random.randint(-300, 0)
        vx = random.uniform(2.0, 3.0)
        vy = 0
        tail = []  # store past positions for path
        line.append([x, y, vx, vy, tail])
    lines.append(line)

running = True
while running:
    screen.fill((0, 0, 0))

    # Input
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        
        elif event.type == pygame.MOUSEWHEEL:
            bh_radius += event.y * 5
            bh_radius = max(10, bh_radius)

    # Drag BH
    if pygame.mouse.get_pressed()[0]:
        bh_x, bh_y = pygame.mouse.get_pos()

    # Update particles
    for line in lines:
        for p in line:
            x, y, vx, vy, tail = p

            dx = bh_x - x
            dy = bh_y - y
            dist = math.hypot(dx, dy)

            # Gravity depends on BH size — IMPORTANT
            # bigger radius = stronger mass
            mass_factor = bh_radius * 0.9

            # Realistic GR-style gravity falloff
            gravity = (gravity_base * mass_factor) / ((dist + 1)**2.1)

            # Unit vectors
            nx = dx / (dist + 0.0001)
            ny = dy / (dist + 0.0001)

            # Curvature vector (perpendicular)
            tx = -ny
            ty = nx

            # Apply bending
            vx += tx * gravity * 0.15
            vy += ty * gravity * 0.15

            # Small inward component
            vx += nx * gravity * 0.02
            vy += ny * gravity * 0.02

            # Update position
            x += vx
            y += vy

            # STORE tail for drawing path
            tail.append((x, y))
            if len(tail) > 300:
                tail.pop(0)

            # Capture radius ~ 1.5 * event horizon
            capture_radius = bh_radius * 1.5
            if dist < capture_radius:
                # Photon is sucked in
                x = -200
                y = random.randint(0, H)
                vx = random.uniform(2.0, 3.0)
                vy = 0
                tail.clear()

            # Reset if too far
            if x > W+200 or y < -200 or y > H+200:
                x = -200
                y = random.randint(0, H)
                vx = random.uniform(2.0, 3.0)
                vy = 0
                tail.clear()

            p[:] = [x, y, vx, vy, tail]

            # Draw the path tail
            for t in tail:
                pygame.draw.circle(screen, (255,255,255), (int(t[0]), int(t[1])), 1)

            # Draw current photon
            pygame.draw.circle(screen, (255, 255, 255), (int(x), int(y)), 2)

    # Draw black hole
    pygame.draw.circle(screen, (0, 0, 0), (bh_x, bh_y), bh_radius)
    pygame.draw.circle(screen, (80, 80, 200), (bh_x, bh_y), bh_radius, 2)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
