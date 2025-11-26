
# Controls summary (new / relevant):
#  - Mouse drag = orbit camera around target (left button)
#  - Scroll wheel = zoom
#  - WASD = pan camera target
#  - Q / E = roll camera
#  - Left-click and drag ON BH projection = move BH (and camera target follows)
#  - [ / ] = decrease / increase visual BH radius
#  - Shift + [ / ] = decrease / increase BH mass (affects gravity)
#  - L = toggle light (sun) on/off
#  - , (comma) = spin disk slower / reverse a bit ; . (period) = spin faster (right)
#  - H / A / O = prepare to place Human / Animal / Object (then type size_cm,mass_kg, Enter, click)
#  - SPACE = pause / R = reset objects & rays / ESC = quit
#
# See HUD at top of window for input hints.
import pygame, sys, math, random
from pygame import Vector3, Vector2
pygame.init()


W, H = 1280, 820
FPS = 60
G = 6.67430e-11
C = 2.99792458e8
LENGTH_SCALE = 6e6       # meters per pixel
PIXELS_PER_METER = 1.0 / LENGTH_SCALE

NUM_LIGHT_RAYS = 700
RAY_STEP_S = 0.004

# BH params
BH_MASS = 6e30
def schwarzschild_radius(m): return 2 * G * m / (C**2)
BH_REAL_RS_M = schwarzschild_radius(BH_MASS)
BH_REAL_RS_PX = max(0.5, BH_REAL_RS_M * PIXELS_PER_METER)
BH_VISUAL_SCALE = 60.0
BH_VISUAL_RADIUS_PX = max(8, int(BH_REAL_RS_PX * BH_VISUAL_SCALE))

# Camera
camera_target = Vector3(0.0, 0.0, 0.0)
cam_dist = 1200.0
cam_yaw = math.radians(0.0)
cam_pitch = math.radians(-10.0)
cam_roll = 0.0
min_cam_dist = 150.0
max_cam_dist = 4000.0
PAN_SPEED = 400.0

# World objects
bh_pos = Vector3(0.0, 0.0, 0.0)
objects = []
light_rays = []
paused = False
placing_mode = None
input_text = ""
next_object_params = None

# Light (sun) initial world position
light_enabled = True
light_world = Vector3(700.0, -250.0, -500.0)  # world coordinates (pixels)
light_screen_radius = 16
disk_spin = 0.9   # spin rate (positive -> clockwise as viewed), adjustable with , and .
disk_angle = 0.0

screen = pygame.display.set_mode((W, H))
clock = pygame.time.Clock()
font = pygame.font.SysFont("Consolas", 16)

# Utilities
def camera_position():
    x = cam_dist * math.cos(cam_pitch) * math.cos(cam_yaw)
    y = cam_dist * math.sin(cam_pitch)
    z = cam_dist * math.cos(cam_pitch) * math.sin(cam_yaw)
    return Vector3(camera_target.x + x, camera_target.y + y, camera_target.z + z)

def make_camera_matrix():
    pos = camera_position()
    forward = (camera_target - pos)
    if forward.length() == 0:
        forward = Vector3(0,0,1)
    forward = forward.normalize()
    up_guess = Vector3(0,1,0)
    right = forward.cross(up_guess)
    if right.length() == 0:
        right = Vector3(1,0,0)
    right = right.normalize()
    up = right.cross(forward).normalize()
    if abs(cam_roll) > 1e-7:
        cosr = math.cos(cam_roll); sinr = math.sin(cam_roll)
        r = right * cosr + up * sinr
        u = -right * sinr + up * cosr
        right, up = r, u
    return pos, forward, right, up

def project_point(world_pt):
    cam_pos, forward, right, up = make_camera_matrix()
    rel = world_pt - cam_pos
    z_cam = rel.dot(forward)
    if z_cam <= 1e-3:
        return None
    x_cam = rel.dot(right); y_cam = rel.dot(up)
    f = 800.0
    sx = (x_cam * f) / z_cam + W/2
    sy = (-y_cam * f) / z_cam + H/2
    return Vector2(sx, sy), z_cam

def accel_due_to_bh_3d(pos_px, bh_mass):
    r_vec = pos_px - bh_pos
    r_px = r_vec.length()
    if r_px < 1e-6: return Vector3(0,0,0)
    r_m = r_px / PIXELS_PER_METER
    a_m_s2 = -G * bh_mass / (r_m**2)
    a_px_s2 = a_m_s2 * PIXELS_PER_METER
    return r_vec.normalize() * a_px_s2

def tidal_strength_3d(pos_px, bh_mass):
    r_px = max(1e-6, (pos_px - bh_pos).length())
    r_m = r_px / PIXELS_PER_METER
    return (G * bh_mass) / (r_m**3 + 1e-12)

# Rays & disk functions
def reset_rays():
    global light_rays
    light_rays = []
    for i in range(NUM_LIGHT_RAYS):
        pos = Vector3(light_world.x + random.uniform(-40,40), light_world.y + random.uniform(-40,40), light_world.z + random.uniform(-40,40))
        dirv = (bh_pos - pos).normalize()
        vel = dirv * (C * PIXELS_PER_METER)
        light_rays.append({'pos': pos, 'vel': vel, 'alive': True, 'path':[pos.copy()], 'intensity':1.0})

def photon_sphere_px_from_mass(m):
    rs_m = schwarzschild_radius(m)
    return max(1.0, 1.5 * rs_m * PIXELS_PER_METER)

def draw_accretion_disk_3d(surface, center_world, inner_px, outer_px, tilt_deg=20, rings=48, spin_angle=0.0):
    tilt = math.radians(tilt_deg)
    for i in range(rings):
        t = i / rings
        r = inner_px + (outer_px - inner_px) * t
        heat = int(230 * (1 - t)**0.7 + 30)
        cold = int(40 * t + 10)
        color = (min(255, 255), min(255, heat), min(255, cold), max(6, int(200 * (1 - t))))
        pts2 = []
        steps = 64
        for a in range(steps):
            ang = (a / steps) * 2*math.pi + spin_angle  # spin applied here
            x = r * math.cos(ang); z = r * math.sin(ang)
            y2 = -z * math.sin(tilt)  # tilt by rotating around X
            z2 = z * math.cos(tilt)
            world_pt = Vector3(center_world.x + x, center_world.y + y2 + int(outer_px*0.02), center_world.z + z2)
            proj = project_point(world_pt)
            if proj is None:
                pts2 = None; break
            pts2.append((proj[0].x, proj[0].y))
        if pts2:
            surf = pygame.Surface((W, H), pygame.SRCALPHA)
            try:
                pygame.draw.polygon(surf, color, pts2)
                surface.blit(surf, (0,0), special_flags=pygame.BLEND_RGBA_ADD)
            except Exception:
                pass

# Updates
reset_rays()
disk_angle = 0.0

def update_objects(dt):
    to_remove = []
    for obj in objects:
        a = accel_due_to_bh_3d(obj['pos'], BH_MASS)
        obj['vel'] += a * dt
        obj['pos'] += obj['vel'] * dt
        r_px = (obj['pos'] - bh_pos).length()
        if r_px <= max(4.0, BH_VISUAL_RADIUS_PX*0.6):
            to_remove.append(obj)
        tidal = tidal_strength_3d(obj['pos'], BH_MASS)
        obj['current_radius'] = max(1.0, obj['base_radius'] / (1.0 + tidal * 4e4))
    for o in to_remove:
        if o in objects: objects.remove(o)

def update_rays(dt):
    for ray in light_rays:
        if not ray['alive']: continue
        steps = max(1, int(dt / RAY_STEP_S))
        for _ in range(steps):
            if not ray['alive']: break
            a = accel_due_to_bh_3d(ray['pos'], BH_MASS)
            ray['vel'] += a * RAY_STEP_S
            s = ray['vel'].length()
            if s == 0: continue
            ray['vel'] = ray['vel'].normalize() * (C * PIXELS_PER_METER)
            ray['pos'] += ray['vel'] * RAY_STEP_S
            ray['path'].append(ray['pos'].copy())
            if len(ray['path']) > 180: ray['path'].pop(0)
            r_px = (ray['pos'] - bh_pos).length()
            # photon sphere bump: use visual scale for comparability
            r_s_ph_px = photon_sphere_px_from_mass(BH_MASS) * BH_VISUAL_SCALE
            if abs(r_px - r_s_ph_px) < max(8.0, r_s_ph_px * 0.06):
                ray['intensity'] = min(20.0, ray.get('intensity',1.0) + 0.08)
            if r_px <= max(4.0, BH_VISUAL_RADIUS_PX * 0.6):
                ray['alive'] = False
            if any(abs(c) > 3000 for c in (ray['pos'].x, ray['pos'].y, ray['pos'].z)):
                ray['alive'] = False

# Input / placement
def place_object_at_3d(screen_pos, type_name, size_cm, mass_kg):
    cam_pos, forward, right, up = make_camera_matrix()
    sx = screen_pos[0] - W/2; sy = -(screen_pos[1] - H/2); f = 800.0
    dir_cam = right * (sx / f) + up * (sy / f) + forward
    denom = dir_cam.dot(forward)
    if abs(denom) < 1e-6:
        t = cam_dist
    else:
        t = (camera_target - cam_pos).dot(forward) / denom
    if t < 0: t = cam_dist
    world_pos = cam_pos + dir_cam * t
    diameter_m = max(0.02, size_cm / 100.0)
    radius_m = diameter_m / 2.0
    radius_px = max(3.0, radius_m * PIXELS_PER_METER)
    objects.append({'pos': world_pos, 'vel': Vector3(0,0,0), 'mass': mass_kg, 'type': type_name, 'base_radius': radius_px, 'current_radius': radius_px})

# Drawing
def draw_scene():
    screen.fill((6,8,14))
    # faint stars
    for i in range(40):
        x = (i * 23 + 7) % W; y = (i * 37 + 13) % H
        screen.set_at((x,y), (18,20,26))

    # draw spinning disk (behind BH)
    disk_surface = pygame.Surface((W,H), pygame.SRCALPHA)
    inner = max(int(BH_VISUAL_RADIUS_PX * 1.5), 8)
    outer = max(int(BH_VISUAL_RADIUS_PX * 6.0), inner+10)
    draw_accretion_disk_3d(disk_surface, bh_pos, inner, outer, tilt_deg=22, rings=56, spin_angle=disk_angle)
    screen.blit(disk_surface, (0,0), special_flags=pygame.BLEND_RGBA_ADD)

    # draw light (sun) if enabled and not occluded
    light_proj = project_point(light_world)
    bh_proj = project_point(bh_pos)
    light_visible = light_enabled
    if light_visible and light_proj and bh_proj:
        # if BH projection overlaps light projection, auto-hide the light to "remove it when it gets in the way"
        light_screen = light_proj[0]
        bh_screen = bh_proj[0]
        if Vector2(light_screen).distance_to(bh_screen) < max( int(BH_VISUAL_RADIUS_PX*0.6), 12 ):
            light_visible = False

    if light_visible and light_proj:
        ls, lz = light_proj
        pygame.draw.circle(screen, (255,245,200), (int(ls.x), int(ls.y)), light_screen_radius)
        # small crescent to show direction (sun shading)
        pygame.draw.circle(screen, (255,235,170), (int(ls.x-6), int(ls.y-6)), 6)

    # black line showing direction from BH to light (highlight area where ring becomes brighter)
    if light_proj and bh_proj:
        ls = light_proj[0]; bs = bh_proj[0]
        # draw black line center outward
        pygame.draw.line(screen, (0,0,0), (int(bs.x), int(bs.y)), (int(ls.x), int(ls.y)), 3)
        # draw wedge hint for ring direction (bright side)
        # wedge located perpendicular to incoming light vector around BH
        v = (ls - bs)
        if v.length() > 1e-6:
            vn = v.normalize()
            perp = Vector2(-vn.y, vn.x)
            wedge_pts = [
                (bs.x, bs.y),
                (bs.x + (vn.x*80 + perp.x*40), bs.y + (vn.y*80 + perp.y*40)),
                (bs.x + (vn.x*120 - perp.x*40), bs.y + (vn.y*120 - perp.y*40)),
            ]
            surf = pygame.Surface((W,H), pygame.SRCALPHA)
            pygame.draw.polygon(surf, (10,10,10,100), wedge_pts)
            screen.blit(surf, (0,0))

    # draw light rays (paths)
    for ray in light_rays:
        if len(ray['path']) > 1:
            pts = []
            for p in ray['path']:
                proj = project_point(p)
                if proj is None:
                    pts = None; break
                pts.append((proj[0].x, proj[0].y))
            if pts:
                inten = min(255, int(40 + ray.get('intensity',1.0)*12))
                try:
                    pygame.draw.aalines(screen, (50, 80, min(255, inten+150)), False, pts)
                except Exception:
                    pass

    # draw objects
    for obj in objects:
        proj = project_point(obj['pos'])
        if proj is None: continue
        screen_pt, zcam = proj
        depth_scale = max(0.06, min(4.0, 1200.0 / (zcam+1e-6)))
        r = max(1, int(obj['current_radius'] * depth_scale))
        col = (140,220,140) if obj['type']=="Human" else (220,170,100) if obj['type']=="Animal" else (160,190,255)
        pygame.draw.circle(screen, col, (int(screen_pt.x), int(screen_pt.y)), r)

    # draw BH visually
    if bh_proj:
        bh_screen, zcam = bh_proj

        # Reduced halo (was too big)
        # make the halo (glow) smaller so the ring remains visible
        halo_scale = 1.15  # reduced from 1.8 previously
        draw_r = max(24, int(BH_VISUAL_RADIUS_PX * halo_scale))
        for i in range(6):  # fewer rings, lower alpha
            alpha = max(0, 20 - i*3)
            rr = draw_r + i*4
            s = pygame.Surface((rr*2+4, rr*2+4), pygame.SRCALPHA)
            # softer, warmer, lower alpha halo
            pygame.draw.circle(s, (240,190,120,alpha), (rr+2, rr+2), rr)
            screen.blit(s, (int(bh_screen.x - rr -2), int(bh_screen.y - rr -2)), special_flags=pygame.BLEND_RGBA_ADD)

        # Spinning bright ring (explicit dots)
        # Draw a clear ring that spins (on top of glow but behind BH core)
        ring_major = max( int(BH_VISUAL_RADIUS_PX * 1.6), 20 )
        ring_minor = max( int(BH_VISUAL_RADIUS_PX * 1.1), 12 )
        ring_color_front = (255, 170, 80)  # bright side
        ring_color_back = (140, 70, 30)    # dimmer side
        # compute direction to light for simple beaming effect
        if light_proj:
            ls = light_proj[0]
            vlight = (ls - bh_screen)
            vlight_norm = vlight.normalize() if vlight.length() > 1e-6 else Vector2(1,0)
        else:
            vlight_norm = Vector2(1,0)

        for ang_deg in range(0, 360, 4):
            rad = math.radians(ang_deg) + disk_angle
            # ellipse coordinates in world-space relative to BH projection
            # horizontal stretch (x) corresponds to ring_major, vertical (y) to ring_minor
            rx = math.cos(rad) * ring_major
            ry = math.sin(rad) * ring_minor
            # rotate ring point by disk tilt around pseudo-axis by using small y-offset
            # create a world point relative to BH in camera space approximation:
            # We'll project a 3D point generated the same way disk uses (approx)
            # For simplicity create a pseudo-world point: offset in local X/Z then project
            # Reuse disk tilt transform used in draw_accretion_disk_3d
            tilt = math.radians(22)
            x = rx
            z = ry
            y2 = -z * math.sin(tilt)
            z2 = z * math.cos(tilt)
            world_pt = Vector3(bh_pos.x + x, bh_pos.y + y2 + int(outer*0.02), bh_pos.z + z2) if 'outer' in globals() else Vector3(bh_pos.x + x, bh_pos.y + y2, bh_pos.z + z2)
            proj = project_point(world_pt)
            if proj is None:
                continue
            screen_pt = proj[0]
            # lighting: dot with light direction to choose color (simple beaming)
            dot = max(-1.0, min(1.0, ((Vector2(screen_pt) - bh_screen).normalize()).dot(vlight_norm)))
            if dot > 0.12:
                col = ring_color_front
                size = 3
            else:
                col = ring_color_back
                size = 2
            pygame.draw.circle(screen, col, (int(screen_pt.x), int(screen_pt.y)), size)

        # Event horizon (solid core)
        vis_r = max(6, int(BH_VISUAL_RADIUS_PX))
        pygame.draw.circle(screen, (8,8,10), (int(bh_screen.x), int(bh_screen.y)), vis_r)
        pygame.draw.circle(screen, (18,18,22), (int(bh_screen.x), int(bh_screen.y)), max(2, vis_r-2), 2)

    # HUD
    def draw_text(s,x,y,c=(220,220,220)): screen.blit(font.render(s, True, c), (x,y))
    draw_text(f"BH mass: {BH_MASS:.2e} kg   r_s (m): {schwarzschild_radius(BH_MASS):.2e}   visual_px: {BH_VISUAL_RADIUS_PX}", 8, 8)
    draw_text("Controls: Mouse drag = orbit | Wheel = zoom | WASD = pan | Q/E = roll | Click-drag BH to move", 8, 26)
    draw_text("L = toggle light | [,] change visual radius | Shift+[ , ] change BH mass (gravity) | ,/. change disk spin", 8, 44)
    draw_text("Place: H=Human (size_cm,mass_kg), A=Animal (length_cm,mass_kg), O=Object (size_cm,mass_kg). Enter then click to place.", 8, 62)
    if placing_mode:
        draw_text(f"Placing: {placing_mode}  | type size_cm,mass_kg  ->  {input_text}", 8, H-28)
    pygame.display.flip()

# Main loop
dragging_orbit = False
last_mouse = None
dragging_bh = False
running = True
reset_rays()

while running:
    dt = clock.tick(FPS) / 1000.0
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT: running = False
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE: running = False
            elif ev.key == pygame.K_SPACE: paused = not paused
            elif ev.key == pygame.K_r:
                objects.clear(); reset_rays()
            elif ev.key == pygame.K_h:
                placing_mode = "Human"; input_text = ""
            elif ev.key == pygame.K_a:
                placing_mode = "Animal"; input_text = ""
            elif ev.key == pygame.K_o:
                placing_mode = "Object"; input_text = ""
            elif ev.key == pygame.K_BACKSPACE and placing_mode:
                input_text = input_text[:-1]
            elif ev.key == pygame.K_RETURN and placing_mode:
                try:
                    parts = [p.strip() for p in input_text.split(',')]
                    if len(parts) >= 2:
                        s_cm = float(parts[0]); mkg = float(parts[1])
                        next_object_params = (placing_mode, s_cm, mkg)
                        input_text = f"Ready: {s_cm}cm, {mkg}kg - click to place"
                    else:
                        input_text = "format: size_cm,mass_kg"
                except:
                    input_text = "parse error"
            elif ev.key == pygame.K_LEFTBRACKET or ev.key == pygame.K_RIGHTBRACKET:
                shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
                if ev.key == pygame.K_LEFTBRACKET:
                    if shift:
                        BH_MASS *= 0.9
                    else:
                        BH_VISUAL_RADIUS_PX = max(4, int(BH_VISUAL_RADIUS_PX * 0.9))
                else:
                    if shift:
                        BH_MASS *= 1.1
                    else:
                        BH_VISUAL_RADIUS_PX = int(BH_VISUAL_RADIUS_PX * 1.1)
                BH_REAL_RS_M = schwarzschild_radius(BH_MASS)
                BH_REAL_RS_PX = max(0.5, BH_REAL_RS_M * PIXELS_PER_METER)
                reset_rays()
            elif ev.key == pygame.K_q: cam_roll -= math.radians(6)
            elif ev.key == pygame.K_e: cam_roll += math.radians(6)
            elif ev.key == pygame.K_l: light_enabled = not light_enabled
            elif ev.key == pygame.K_COMMA:
                disk_spin -= 0.12
            elif ev.key == pygame.K_PERIOD:
                disk_spin += 0.12
        elif ev.type == pygame.TEXTINPUT and placing_mode:
            input_text += ev.text
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1:
                last_mouse = ev.pos
                proj = project_point(bh_pos)
                if proj:
                    sp, z = proj
                    if Vector2(ev.pos).distance_to(sp) <= max(8, BH_VISUAL_RADIUS_PX):
                        dragging_bh = True
                    else:
                        dragging_orbit = True
            elif ev.button == 3:
                paused = not paused
            elif ev.button == 4:
                cam_dist = max(min_cam_dist, cam_dist * 0.92)
            elif ev.button == 5:
                cam_dist = min(max_cam_dist, cam_dist * 1.08)
        elif ev.type == pygame.MOUSEBUTTONUP:
            if ev.button == 1:
                if next_object_params and not dragging_bh:
                    # place object at click
                    try:
                        mx,my = ev.pos
                        t,s,m = next_object_params
                        place_object_at_3d((mx,my), t, s, m)
                        next_object_params = None; placing_mode = None; input_text = ""
                    except:
                        pass
                dragging_orbit = False; dragging_bh = False
        elif ev.type == pygame.MOUSEMOTION:
            if dragging_orbit and last_mouse:
                mx,my = ev.pos; lx,ly = last_mouse; dx = mx-lx; dy = my-ly
                cam_yaw += dx * 0.003; cam_pitch += dy * 0.003
                cam_pitch = max(math.radians(-89.0), min(math.radians(89.0), cam_pitch))
                last_mouse = ev.pos
            elif dragging_bh and last_mouse:
                mx,my = ev.pos
                cam_pos, forward, right, up = make_camera_matrix()
                sx = mx - W/2; sy = -(my - H/2); f = 800.0
                dir_cam = right * (sx / f) + up * (sy / f) + forward
                if dir_cam.length() == 0: continue
                dir_cam = dir_cam.normalize()
                denom = dir_cam.dot(forward)
                if abs(denom) < 1e-6: t = cam_dist
                else: t = (camera_target - cam_pos).dot(forward) / denom
                if t < 0: t = cam_dist
                new_world = cam_pos + dir_cam * t
                offset = new_world - bh_pos
                bh_pos.x += offset.x; bh_pos.y += offset.y; bh_pos.z += offset.z
                camera_target.x += offset.x; camera_target.y += offset.y; camera_target.z += offset.z
                last_mouse = ev.pos
            else:
                last_mouse = ev.pos

    # continuous pan
    keys = pygame.key.get_pressed()
    move = Vector3(0,0,0)
    if keys[pygame.K_w]: move += Vector3(0, -PAN_SPEED*dt, 0)
    if keys[pygame.K_s]: move += Vector3(0, PAN_SPEED*dt, 0)
    if keys[pygame.K_a]: move += Vector3(-PAN_SPEED*dt, 0, 0)
    if keys[pygame.K_d]: move += Vector3(PAN_SPEED*dt, 0, 0)
    if move.length() > 0:
        _, forward, right, up = make_camera_matrix()
        camera_target += right * move.x + up * (-move.y)

    if not paused:
        update_objects(dt)
        update_rays(dt)
        # rotate disk according to spin
        disk_angle += disk_spin * dt

    draw_scene()

pygame.quit()
sys.exit()

# Nov/26/2025
# Problem & issue failed attempt in playing pysics and it makes different outcome, low image output can't do 3d rendering well(maybe it's because pygame engine build in itself)
# Pygame can only handle simple game instead of graphics focus, it slows down as I use for range(whatever number probably higher than 100 like monte carlo) seems to be too much for it to handle
# Maybe I should consider using unity engine. 
# What I'm aiming in this refix that I recently fail yesterday is light direction in blackhole where light bends but, that light is ray pigments(maybe we called it as photons like the previous file in photon_path.py which it works fine but not as satisfied, but whatever)
# Also I want object input(you see the permanent black line, that is where object goes, directed to the black hole) that is where the object should start and end. 
# don't ask about the graphics. I can't explain how to draw actual 3d blackhole like in space. mainly, the blackhole isn't the issue as it was only a black circle as for the equation, I never use the actual equation(except schwarzschild radius is required) but, i used mostly some of the effect since I understand it. 
# how does light(photon) bends the image of the black hole? that is impossible but I was still trying to figure that out
# along with object with gravity influence would even destroy the equation of how it looks(I'm overthinking it).
# I'd say, the python project in pygame is a quit but the project isn't a fail yet
# for the python courses, I use only import pygame, math, sys, random
# as for position, direction and velocity in 3d map, I used vector import to pygame. 
# the for loop is used for light rays, objects, and the ring surounded the blackhole(you probably read the code and thought in def draw_accretion_disk_3d)
# if statement, I don't need to explain this
# there are updates from the one I left yesterday and I continue again(unimportant)
# for function, there is the function for camera, input object, and function of the blackhole itself(to be short)
# im too sure anyone reading this without any knowledge of physics, will never able to understand this even if they are a very exceptional programmer
# oh, and the only thing I did was making it in format short but slightly readable. 
