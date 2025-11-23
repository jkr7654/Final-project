import pygame
import sys
import math
import random
#import pygame, time, sys, random, math
pygame.init()
width, height = 1100, 800
screen = pygame.display.set_mode((width, height))
clock = pygame.time.Clock()
#screen opening
N = 4000 # total stars/particles that goes in random uniform axis 
particles = []
for i in range(N):
    # start in a spherical shell biased at radius
    r = random.uniform(120, 520)
    theta = random.uniform(0, math.pi)
    phi = random.uniform(0, 2*math.pi)
    x = r * math.sin(theta) * math.cos(phi)
    y = r * math.sin(theta) * math.sin(phi)
    z = r * math.cos(theta)
    # angular momentum to create swirl
    spin = (random.random()*0.6 + 0.4) * (1 if random.random()>0.5 else -1)
    speed = 0.0009 + 0.0006*random.random()
    particles.append([x,y,z, spin, speed, r])
# camera
yaw = 0.0
pitch = 0.0
zoom = 1.0
dragging = False
last = (0,0)
def rotate(x,y,z, yaw, pitch):
    cy, sy = math.cos(yaw), math.sin(yaw)
    x1 = x*cy - z*sy
    z1 = x*sy + z*cy
    cp, sp = math.cos(pitch), math.sin(pitch)
    y1 = y*cp - z1*sp
    z2 = y*sp + z1*cp
    return x1,y1,z2
def project(x,y,z):
    zc = z + 800
    if zc <= 0.1: zc = 0.1
    f = 900 * zoom / zc
    sx = int(width/2 + x * f)
    sy = int(height/2 - y * f)
    return sx, sy, zc
running = True
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT: running=False
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1:
                dragging = True
                last = ev.pos
            elif ev.button == 4: zoom *= 1.06
            elif ev.button == 5: zoom /= 1.06
        elif ev.type == pygame.MOUSEBUTTONUP:
            if ev.button == 1: dragging=False
        elif ev.type == pygame.MOUSEMOTION and dragging:
            mx,my = ev.pos
            dx = mx-last[0]; dy = my-last[1]
            yaw += dx * 0.005
            pitch += dy * 0.005
            last = (mx,my)
        elif ev.type == pygame.KEYDOWN:
            if ev.key==pygame.K_w: zoom*=1.06
            if ev.key==pygame.K_s: zoom/=1.06
            if ev.key==pygame.K_ESCAPE: running=False

    screen.fill((0,0,0))

    # update physics: spiral inward with angular motion (conserve r-ish)
    for p in particles:
        x,y,z,spin,speed,r0 = p
        # convert to cylindrical coords relative to center axis (z)
        rho = math.sqrt(x*x + y*y) + 1e-6
        # angular velocity inversely related to radius
        ang_vel = spin * (0.0025/(rho*0.01 + 1.0))
        # advance angle around z axis
        ang = math.atan2(y, x) + ang_vel
        # radial fall-in
        fall = 0.06 * (1.0/(rho*0.01 + 0.5))
        rho -= fall
        # push a little toward midplane (z->0) for disk formation
        z *= 0.997
        # update back to cartesian
        x = rho * math.cos(ang)
        y = rho * math.sin(ang)
        # if too close respawn at outer shell
        if rho < 6:
            # respawn
            r = random.uniform(220, 520)
            theta = random.uniform(0, math.pi)
            phi = random.uniform(0, 2*math.pi)
            x = r * math.sin(theta) * math.cos(phi)
            y = r * math.sin(theta) * math.sin(phi)
            z = r * math.cos(theta)
            p[3] = (random.random()*0.6 + 0.4) * (1 if random.random()>0.5 else -1)
        p[0], p[1], p[2] = x,y,z

    # draw particles (sorted by depth for simple painter)
    proj_list = []
    for p in particles:
        x,y,z = p[0], p[1], p[2]
        xr, yr, zr = rotate(x,y,z, yaw, pitch)
        sx, sy, zc = project(xr, yr, zr)
        # brightness based on zc (nearer brighter) and radial
        bright = int(max(10, min(255, 300 - (zc*0.12))))
        proj_list.append((zc, sx, sy, bright))

    proj_list.sort(reverse=True, key=lambda x: x[0])
    for zc, sx, sy, bright in proj_list:
        if 0 <= sx < width and 0 <= sy < height:
            # small dot, larger when near
            size = 1 if zc>700 else 2 if zc>550 else 3
            col = (bright, min(220, bright//1.3), int(bright*0.7))
            pygame.draw.circle(screen, col, (sx,sy), size)

    # draw central black disk (singularity)
    pygame.draw.circle(screen, (0,0,0), (width//2, height//2), int(40*zoom))
    pygame.display.flip()
    clock.tick(60)
pygame.quit()
sys.exit()
#date/nov/23/2025
